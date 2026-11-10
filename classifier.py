import os
from pathlib import Path
from config import (
    WEIGHT_KNOWN_CACHE_TEMP_DIR,
    WEIGHT_PROCESS_INACTIVE,
    WEIGHT_AGE_ABOVE_THRESHOLD,
    WEIGHT_TEMP_FILE_PATTERN,
    WEIGHT_FILE_ACCESSIBLE,
    CLASSIFICATION_ZOMBIE,
    CLASSIFICATION_UNCERTAIN,
    CLASSIFICATION_KEEP,
    SCORE_THRESHOLD_ZOMBIE,
    SCORE_THRESHOLD_UNCERTAIN,
    PROTECTED_FILE_PATTERNS,
    PROTECTED_EXTENSIONS,
    TEMP_CACHE_EXTENSIONS,
    KNOWN_CACHE_DIR_KEYWORDS,
    DEFAULT_AGE_THRESHOLD_DAYS,
)
from utils import calculate_file_age_days

class ZombieDataClassifier:
    """
    Module 2 – Zombie Data Intelligence and Classification
    Task 2.1 – Zombie Data Analysis:
      Activity 2.1.1: File age analysis.
      Activity 2.1.2: Access and modification pattern analysis.
      Activity 2.1.3: Cache characteristics evaluation.
    Task 2.2 – Intelligent Classification Engine:
      Activity 2.2.1: Explainable zombie score calculation.
      Activity 2.2.2: Risk category classification.
      Activity 2.2.3: Classification reason generation.
    """

    @staticmethod
    def analyze_file_age(mtime: float, ctime: float, threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS) -> dict:
        """
        Activity 2.1.1: File age analysis.
        Calculates file age from modification and creation timestamps.
        """
        age_days = calculate_file_age_days(mtime)
        creation_age_days = calculate_file_age_days(ctime)
        exceeds = age_days >= threshold_days
        
        return {
            "age_days": age_days,
            "creation_age_days": creation_age_days,
            "threshold_days": threshold_days,
            "exceeds_threshold": exceeds,
            "age_score_contribution": WEIGHT_AGE_ABOVE_THRESHOLD if exceeds else 0
        }

    @staticmethod
    def analyze_access_modification_patterns(metadata: dict) -> dict:
        """
        Activity 2.1.2: Access and modification pattern analysis.
        Checks if the file is currently locked/accessible and if the parent process is active.
        """
        process_running = metadata.get("process_running", False)
        accessible = metadata.get("accessible", True)
        
        # Process inactive is a strong signal that files can be evaluated safely
        proc_contribution = WEIGHT_PROCESS_INACTIVE if process_running is False else 0
        access_contribution = WEIGHT_FILE_ACCESSIBLE if accessible else 0

        return {
            "process_running": process_running,
            "accessible": accessible,
            "process_score_contribution": proc_contribution,
            "access_score_contribution": access_contribution,
            "is_dormant": (not process_running) and accessible
        }

    @staticmethod
    def evaluate_cache_characteristics(metadata: dict) -> dict:
        """
        Activity 2.1.3: Cache characteristics evaluation.
        Evaluates whether directory structure and filename patterns match known disposable cache artifacts.
        """
        full_path = metadata.get("full_path", "").lower()
        file_name = metadata.get("file_name", "").lower()
        extension = metadata.get("extension", "").lower()

        in_cache_dir = any(keyword in full_path for keyword in KNOWN_CACHE_DIR_KEYWORDS)
        cache_dir_contribution = WEIGHT_KNOWN_CACHE_TEMP_DIR if in_cache_dir else 0

        is_temp_pattern = extension in TEMP_CACHE_EXTENSIONS or "temp" in file_name or "cache" in file_name
        pattern_contribution = WEIGHT_TEMP_FILE_PATTERN if is_temp_pattern else 0

        matched_keywords = [kw for kw in KNOWN_CACHE_DIR_KEYWORDS if kw in full_path]

        return {
            "in_cache_dir": in_cache_dir,
            "matched_cache_keywords": matched_keywords,
            "is_temp_pattern": is_temp_pattern,
            "cache_dir_contribution": cache_dir_contribution,
            "pattern_contribution": pattern_contribution,
            "is_disposable_cache": in_cache_dir or is_temp_pattern
        }

    @classmethod
    def calculate_zombie_score(cls, metadata: dict, age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS) -> dict:
        """
        Activity 2.2.1: Explainable zombie score calculation.
        Computes 0 to 100 deterministic score with explainable factor breakdown.
        """
        file_name = metadata.get("file_name", "").lower()
        full_path = metadata.get("full_path", "").lower()
        extension = metadata.get("extension", "").lower()

        # Check safety whitelist first
        for protected_pattern in PROTECTED_FILE_PATTERNS:
            if protected_pattern in file_name or protected_pattern in full_path:
                return {
                    "score": 0,
                    "is_protected": True,
                    "protection_reason": f"Protected pattern match ('{protected_pattern}') — Essential browser/user database.",
                    "factors": {}
                }

        for protected_ext in PROTECTED_EXTENSIONS:
            if extension == protected_ext:
                return {
                    "score": 0,
                    "is_protected": True,
                    "protection_reason": f"Protected extension ('{protected_ext}') — Security/credential file.",
                    "factors": {}
                }

        # Sub-analyses
        age_analysis = cls.analyze_file_age(metadata.get("mtime", 0), metadata.get("ctime", 0), age_threshold_days)
        pattern_analysis = cls.analyze_access_modification_patterns(metadata)
        cache_eval = cls.evaluate_cache_characteristics(metadata)

        score = (
            cache_eval["cache_dir_contribution"] +
            pattern_analysis["process_score_contribution"] +
            age_analysis["age_score_contribution"] +
            cache_eval["pattern_contribution"] +
            pattern_analysis["access_score_contribution"]
        )

        return {
            "score": min(100, max(0, score)),
            "is_protected": False,
            "protection_reason": None,
            "factors": {
                "cache_directory": cache_eval["cache_dir_contribution"],
                "process_inactive": pattern_analysis["process_score_contribution"],
                "age_threshold": age_analysis["age_score_contribution"],
                "temp_pattern": cache_eval["pattern_contribution"],
                "file_accessible": pattern_analysis["access_score_contribution"],
            },
            "age_analysis": age_analysis,
            "pattern_analysis": pattern_analysis,
            "cache_eval": cache_eval
        }

    @staticmethod
    def classify_risk_category(score: int, is_protected: bool = False) -> tuple:
        """
        Activity 2.2.2: Risk category classification.
        Maps score into risk severity level and classification label.
        """
        if is_protected:
            return CLASSIFICATION_KEEP, "LOW_RISK_PROTECTED"
        elif score >= SCORE_THRESHOLD_ZOMBIE:
            return CLASSIFICATION_ZOMBIE, "CRITICAL_ZOMBIE_CANDIDATE"
        elif score >= SCORE_THRESHOLD_UNCERTAIN:
            return CLASSIFICATION_UNCERTAIN, "MODERATE_UNCERTAIN"
        else:
            return CLASSIFICATION_KEEP, "LOW_RISK_ACTIVE"

    @classmethod
    def generate_classification_reasons(cls, metadata: dict, score_data: dict, age_threshold_days: int) -> dict:
        """
        Activity 2.2.3: Classification reason generation.
        Produces human-readable positive factors, negative factors, confidence metric, and recommendation.
        """
        if score_data.get("is_protected"):
            return {
                "reasons": [score_data["protection_reason"]],
                "increasing_factors": [],
                "decreasing_factors": ["Matches protected data whitelist pattern (Hard Immunity)"],
                "confidence": 1.0,
                "confidence_percentage": "100%",
                "recommendation": "DO NOT DELETE — Protected user data"
            }

        reasons = []
        increasing = []
        decreasing = []
        factors = score_data.get("factors", {})

        # 1. Cache Context
        if factors.get("cache_directory", 0) > 0:
            reasons.append(f"+{WEIGHT_KNOWN_CACHE_TEMP_DIR} Known Cache/Temp/Log directory context")
            increasing.append("Located in disposable cache subdirectory")
        else:
            reasons.append(" 0 Path is outside known cache keywords")
            decreasing.append("Path is not in standard cache directory")

        # 2. Process
        if factors.get("process_inactive", 0) > 0:
            reasons.append(f"+{WEIGHT_PROCESS_INACTIVE} Associated application process is inactive (not running)")
            increasing.append("Application is closed, ensuring safe file handling")
        elif metadata.get("process_running") is True:
            reasons.append(" 0 Application process is currently running")
            decreasing.append("Application process is active (file might be in active use)")
        else:
            reasons.append(" 0 Application process status is unknown")

        # 3. Age
        age_days = metadata.get("age_days", 0)
        if factors.get("age_threshold", 0) > 0:
            reasons.append(f"+{WEIGHT_AGE_ABOVE_THRESHOLD} File age ({age_days} days) exceeds threshold ({age_threshold_days} days)")
            increasing.append(f"Dormant for {age_days} days (threshold {age_threshold_days} days)")
        else:
            reasons.append(f" 0 File age ({age_days} days) is recent (< {age_threshold_days} days)")
            decreasing.append("File was recently created or modified")

        # 4. Pattern
        ext = metadata.get("extension", "")
        if factors.get("temp_pattern", 0) > 0:
            reasons.append(f"+{WEIGHT_TEMP_FILE_PATTERN} Temporary/cache file pattern or extension match ('{ext}')")
            increasing.append(f"Extension '{ext}' matches known temporary/cache signature")
        else:
            decreasing.append(f"Extension '{ext}' is non-standard for cache")

        # 5. Accessibility
        if factors.get("file_accessible", 0) > 0:
            reasons.append(f"+{WEIGHT_FILE_ACCESSIBLE} File is accessible (unlocked by system)")
            increasing.append("File is unlocked and readable")
        else:
            decreasing.append("File is locked by OS or inaccessible")

        # Confidence heuristic based on number of positive signals
        positive_count = sum(1 for v in factors.values() if v > 0)
        confidence = round(0.50 + (positive_count * 0.10), 2)
        score = score_data.get("score", 0)

        if score >= SCORE_THRESHOLD_ZOMBIE:
            recommendation = "Eligible for quarantine review (High zombie confidence)"
        elif score >= SCORE_THRESHOLD_UNCERTAIN:
            recommendation = "Retain for observation; manual inspection suggested"
        else:
            recommendation = "Keep in place (Low probability of stale cache)"

        return {
            "reasons": reasons,
            "increasing_factors": increasing,
            "decreasing_factors": decreasing,
            "confidence": confidence,
            "confidence_percentage": f"{int(confidence * 100)}%",
            "recommendation": recommendation
        }

    @classmethod
    def classify_file(cls, file_metadata: dict, age_threshold_days: int = DEFAULT_AGE_THRESHOLD_DAYS) -> dict:
        """
        Unified classification pipeline executing Tasks 2.1 & 2.2.
        Backward compatible with previous API.
        """
        score_data = cls.calculate_zombie_score(file_metadata, age_threshold_days)
        score = score_data["score"]
        is_protected = score_data.get("is_protected", False)
        
        classification, risk_level = cls.classify_risk_category(score, is_protected)
        reasons_data = cls.generate_classification_reasons(file_metadata, score_data, age_threshold_days)

        return {
            "score": score,
            "classification": classification,
            "risk_level": risk_level,
            "reasons": reasons_data["reasons"],
            "factors": score_data.get("factors", {}),
            "increasing_factors": reasons_data["increasing_factors"],
            "decreasing_factors": reasons_data["decreasing_factors"],
            "confidence": reasons_data["confidence"],
            "confidence_percentage": reasons_data["confidence_percentage"],
            "recommendation": reasons_data["recommendation"]
        }
