"""Local SQLite store for durable scan, quarantine, and cleanup audit history."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

from config import REAL_BASE_DIR


class AuditStore:
    def __init__(self, db_path=None):
        self.db_path = str(db_path or Path(REAL_BASE_DIR) / "zombie_data_purger.sqlite3")
        self.initialize()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scan_sessions (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    app_name TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    scanned_count INTEGER NOT NULL,
                    zombie_count INTEGER NOT NULL,
                    uncertain_count INTEGER NOT NULL,
                    keep_count INTEGER NOT NULL,
                    potential_bytes INTEGER DEFAULT 0,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    id INTEGER PRIMARY KEY,
                    scan_id INTEGER NOT NULL REFERENCES scan_sessions(id) ON DELETE CASCADE,
                    path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    classification TEXT NOT NULL,
                    risk_level TEXT DEFAULT 'UNKNOWN',
                    sha256_hash TEXT DEFAULT '',
                    is_duplicate INTEGER DEFAULT 0,
                    reasons_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    operation_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    code TEXT NOT NULL,
                    source_path TEXT,
                    destination_path TEXT,
                    detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quarantine_records (
                    id INTEGER PRIMARY KEY,
                    quarantine_id TEXT UNIQUE NOT NULL,
                    mode TEXT NOT NULL,
                    original_path TEXT NOT NULL,
                    quarantine_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    sha256_hash TEXT NOT NULL,
                    quarantined_at TEXT NOT NULL,
                    status TEXT NOT NULL, -- 'QUARANTINED', 'RESTORED', 'PURGED'
                    retention_days INTEGER DEFAULT 30,
                    restored_at TEXT,
                    purged_at TEXT
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS audit_events_created_at ON audit_events(created_at);
                CREATE INDEX IF NOT EXISTS scan_sessions_created_at ON scan_sessions(created_at);
                CREATE INDEX IF NOT EXISTS quarantine_records_status ON quarantine_records(status);
            """)

            # Migration check: Ensure new columns exist on older databases
            scan_cols = [c[1] for c in conn.execute("PRAGMA table_info(scan_sessions)").fetchall()]
            if "potential_bytes" not in scan_cols:
                conn.execute("ALTER TABLE scan_sessions ADD COLUMN potential_bytes INTEGER DEFAULT 0")

            cand_cols = [c[1] for c in conn.execute("PRAGMA table_info(candidates)").fetchall()]
            if "risk_level" not in cand_cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN risk_level TEXT DEFAULT 'UNKNOWN'")
            if "sha256_hash" not in cand_cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN sha256_hash TEXT DEFAULT ''")
            if "is_duplicate" not in cand_cols:
                conn.execute("ALTER TABLE candidates ADD COLUMN is_duplicate INTEGER DEFAULT 0")

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def record_scan(self, mode, result):
        """Persist scan summary and per-file classification atomically."""
        scan_error = result.get("error")
        if result.get("issues"):
            scan_error = json.dumps({"error": scan_error, "issues": result["issues"]}, ensure_ascii=False)
        if result.get("cancelled"):
            scan_error = json.dumps({"error": scan_error, "cancelled": True}, ensure_ascii=False)
        
        potential_bytes = int(result.get("potential_reclaimable_bytes", 0))

        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO scan_sessions(created_at,mode,app_name,target_path,scanned_count,zombie_count,uncertain_count,keep_count,potential_bytes,error) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (self._now(), mode, result.get("app_name", ""), result.get("target_path", ""),
                 int(result.get("scanned_count", 0)), int(result.get("zombie_count", 0)),
                 int(result.get("uncertain_count", 0)), int(result.get("keep_count", 0)), potential_bytes, scan_error),
            )
            scan_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO candidates(scan_id,path,size_bytes,score,classification,risk_level,sha256_hash,is_duplicate,reasons_json) VALUES(?,?,?,?,?,?,?,?,?)",
                [(scan_id, f.get("full_path", ""), int(f.get("size_bytes", 0)), int(f.get("score", 0)),
                  f.get("classification", ""), f.get("risk_level", "NORMAL"),
                  f.get("sha256", ""), 1 if f.get("is_duplicate") else 0,
                  json.dumps(f.get("reasons", []), ensure_ascii=False))
                 for f in result.get("files", [])],
            )
            return scan_id

    def record_event(self, operation, mode, decision, code, detail,
                     source_path=None, destination_path=None, operation_id=None):
        """Persist a cleanup decision/result without storing file contents."""
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO audit_events(created_at,operation_id,operation,mode,decision,code,source_path,destination_path,detail) VALUES(?,?,?,?,?,?,?,?,?)",
                (self._now(), operation_id or str(uuid.uuid4()), operation, mode, decision, code,
                 source_path, destination_path, str(detail)),
            )
            return cur.lastrowid

    def record_quarantine(self, quarantine_id, mode, original_path, quarantine_path, file_size, sha256_hash, retention_days=30):
        """Records a new quarantined file entry."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO quarantine_records (quarantine_id, mode, original_path, quarantine_path, file_size, sha256_hash, quarantined_at, status, retention_days)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'QUARANTINED', ?)
                   ON CONFLICT(quarantine_id) DO UPDATE SET
                   status='QUARANTINED', quarantine_path=excluded.quarantine_path, quarantined_at=excluded.quarantined_at""",
                (quarantine_id, mode, original_path, quarantine_path, file_size, sha256_hash, self._now(), retention_days)
            )

    def update_quarantine_status(self, quarantine_id, status):
        """Updates quarantine status to RESTORED or PURGED."""
        now = self._now()
        with self._connect() as conn:
            if status == "RESTORED":
                conn.execute("UPDATE quarantine_records SET status=?, restored_at=? WHERE quarantine_id=?", (status, now, quarantine_id))
            elif status == "PURGED":
                conn.execute("UPDATE quarantine_records SET status=?, purged_at=? WHERE quarantine_id=?", (status, now, quarantine_id))
            else:
                conn.execute("UPDATE quarantine_records SET status=? WHERE quarantine_id=?", (status, quarantine_id))

    def list_events(self, limit=100):
        with self._connect() as conn:
            return conn.execute(
                "SELECT created_at,operation_id,operation,mode,decision,code,source_path,destination_path,detail FROM audit_events ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()

    def list_scans(self, limit=100):
        with self._connect() as conn:
            return conn.execute(
                "SELECT created_at,mode,app_name,target_path,scanned_count,zombie_count,uncertain_count,keep_count,error FROM scan_sessions ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 1000)),),
            ).fetchall()

    def list_quarantine_records(self, mode=None):
        with self._connect() as conn:
            if mode:
                rows = conn.execute(
                    "SELECT quarantine_id, mode, original_path, quarantine_path, file_size, sha256_hash, quarantined_at, status, retention_days, restored_at, purged_at FROM quarantine_records WHERE mode=? ORDER BY id DESC",
                    (mode,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT quarantine_id, mode, original_path, quarantine_path, file_size, sha256_hash, quarantined_at, status, retention_days, restored_at, purged_at FROM quarantine_records ORDER BY id DESC"
                ).fetchall()
            return [
                {
                    "quarantine_id": r[0], "mode": r[1], "original_path": r[2], "quarantine_path": r[3],
                    "file_size": r[4], "sha256": r[5], "quarantined_at": r[6], "status": r[7],
                    "retention_days": r[8], "restored_at": r[9], "purged_at": r[10]
                }
                for r in rows
            ]

    def get_dashboard_metrics(self):
        """Computes live aggregated metrics from all scans and quarantine operations."""
        with self._connect() as conn:
            scan_stats = conn.execute("""
                SELECT 
                    COALESCE(SUM(scanned_count), 0),
                    COALESCE(SUM(zombie_count), 0),
                    COALESCE(SUM(uncertain_count), 0),
                    COALESCE(SUM(keep_count), 0),
                    COALESCE(SUM(potential_bytes), 0),
                    COUNT(id)
                FROM scan_sessions
            """).fetchone()

            quarantine_stats = conn.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN status='QUARANTINED' THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN status='RESTORED' THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN status='PURGED' THEN 1 ELSE 0 END), 0),
                    COALESCE(SUM(CASE WHEN status='QUARANTINED' THEN file_size ELSE 0 END), 0)
                FROM quarantine_records
            """).fetchone()

            audit_count = conn.execute("SELECT COUNT(id) FROM audit_events").fetchone()[0]

            return {
                "total_scanned_files": scan_stats[0],
                "total_zombies": scan_stats[1],
                "total_uncertain": scan_stats[2],
                "total_keep": scan_stats[3],
                "potential_reclaimable_bytes": scan_stats[4],
                "total_scan_sessions": scan_stats[5],
                "quarantined_count": quarantine_stats[0],
                "restored_count": quarantine_stats[1],
                "purged_count": quarantine_stats[2],
                "quarantined_bytes": quarantine_stats[3],
                "total_audit_events": audit_count,
            }

    def get_risk_distribution(self):
        """Returns risk distribution counts across all candidate files."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT classification, COUNT(id) 
                FROM candidates 
                GROUP BY classification
            """).fetchall()
            dist = {"ZOMBIE": 0, "UNCERTAIN": 0, "KEEP": 0}
            for cls_name, count in rows:
                if "ZOMBIE" in cls_name.upper():
                    dist["ZOMBIE"] += count
                elif "UNCERTAIN" in cls_name.upper():
                    dist["UNCERTAIN"] += count
                else:
                    dist["KEEP"] += count
            return dist

    def get_app_cache_breakdown(self):
        """Returns application cache breakdown statistics."""
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT app_name, 
                       COALESCE(SUM(scanned_count), 0), 
                       COALESCE(SUM(zombie_count), 0), 
                       COALESCE(SUM(potential_bytes), 0)
                FROM scan_sessions
                GROUP BY app_name
                ORDER BY SUM(potential_bytes) DESC
            """).fetchall()
            return [
                {"app_name": r[0], "scanned_files": r[1], "zombie_files": r[2], "reclaimable_bytes": r[3]}
                for r in rows
            ]

    def get_scan_trend(self, days=7):
        """Returns daily trend data for the last N days."""
        trend = []
        today = datetime.now(timezone.utc).date()
        with self._connect() as conn:
            for i in range(days - 1, -1, -1):
                target_date = today - timedelta(days=i)
                date_str = target_date.isoformat()
                row = conn.execute("""
                    SELECT COALESCE(SUM(scanned_count), 0), COALESCE(SUM(zombie_count), 0), COALESCE(SUM(potential_bytes), 0)
                    FROM scan_sessions
                    WHERE created_at LIKE ?
                """, (f"{date_str}%",)).fetchone()
                trend.append({
                    "date": target_date.strftime("%b %d"),
                    "scanned": row[0],
                    "zombies": row[1],
                    "reclaimable_bytes": row[2]
                })
        return trend

    def get_setting(self, key, default=None):
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return default if row is None else row[0]

    def set_setting(self, key, value):
        with self._connect() as conn:
            conn.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                         (key, str(value), self._now()))


_default_store = None


def get_audit_store():
    global _default_store
    if _default_store is None:
        _default_store = AuditStore()
    return _default_store
