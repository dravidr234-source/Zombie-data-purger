# Safety and recovery design

## Authorization

`safety_policy.py` is the sole authorization service for quarantine, restore, and purge. It returns `ALLOW`, `DENY`, or `REQUIRE_REVIEW`, with a stable reason code. The GUI and background scan worker call `QuarantineManager`; neither implements its own file move or deletion authorization.

Real quarantine requires all of the following: a reviewed application root and cache layout; a disposable extension; age of at least 14 days; a current, matching device/inode/size/modification-time snapshot; a confirmed stopped application; no matching protected-data rule; an exclusive open check; and a destination inside the application quarantine. Any unknown fact blocks the operation. Demo cleanup is confined to the synthetic sandbox.

The process monitor is read-only. Process suspend, resume, terminate, and kill APIs are not implemented by the active application service. The legacy class name `TaskSuspender` remains as a compatibility stub that always refuses process control.

## File operation order

1. Scan and record metadata without changing files.
2. Reauthorize immediately before quarantine; check file identity and exclusive access.
3. Hash the file, move it into quarantine, and verify the destination hash.
4. Atomically replace the JSON manifest and record the operation in SQLite.
5. If verification or manifest persistence fails, attempt to move the file back and report its location if rollback fails.
6. Restore only from a valid manifest entry, verify its hash, refuse destination collisions, and record the outcome.
7. Purge only from the quarantine directory, only after the configured 30-day retention, and only when the user explicitly enabled the policy. The global pause blocks quarantine, restore, and purge.

## Persistence

SQLite is stored under `%LOCALAPPDATA%\ZombieDataPurger\`. `CREATE TABLE IF NOT EXISTS` initializes scan sessions, candidate metadata, audit events, and settings. Scan/candidate writes are transactional. Quarantine manifests use a temporary file, flush, `fsync`, and `os.replace`.

## Recovery limits

Operation exceptions trigger immediate rollback attempts. If rollback fails, the app reports the last known path. The JSON manifest is the restoration index; unreadable or malformed manifests block operations. There is not yet a startup reconciler that compares every quarantine file against the manifest after sudden power loss. Keep an independent backup of any file before enabling automated cleanup on a production profile.

## Monitoring and resource limits

Disk scans are read-only and periodic (15 minutes) when explicitly started or when an automatic cleanup policy was previously enabled. Scans cap at 2,500 files per application and only descend through reviewed cache layouts. Filesystem change notifications are not implemented. The process monitor polls on its configured interval and never changes process state.
