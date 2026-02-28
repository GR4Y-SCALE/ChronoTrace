"""
ChronoTrace — 15 NTFS Anti-Forensics Detection Rules
Each rule evaluates a specific anomaly pattern from the correlated file data.
"""

from typing import Dict, Any, List
from datetime import datetime

RULES = {
    "RULE_01": {
        "name": "SI_FN_DIVERGENCE",
        "severity": "CRITICAL",
        "description": "abs(SI_modified - FN_modified) > 1 hour",
        "explanation": "Timestamp backdating strongly indicated. $SI (Standard Information) and $FN (File Name) timestamps have diverged significantly.",
        "category": "Timestamp",
    },
    "RULE_02": {
        "name": "BACKDATING_DETECTED",
        "severity": "CRITICAL",
        "description": "SI_modified < FN_created on this volume",
        "explanation": "File modified before it existed on this device. Strong indicator of timestomping prior to a cross-device transfer.",
        "category": "Timestamp",
    },
    "RULE_03": {
        "name": "MISSING_USN_HISTORY",
        "severity": "HIGH",
        "description": "USN shows only FILE_CREATE, SI shows prior edits",
        "explanation": "History wiped or file arrived pre-manipulated. The update sequence number journal does not reflect the modifications claimed by the $SI attribute.",
        "category": "Log Evasion",
    },
    "RULE_04": {
        "name": "LSN_SEQUENCE_BREAK",
        "severity": "HIGH",
        "description": "LogFile LSN non-sequential or gap too large",
        "explanation": "Log tampering or external file origin. The Log Sequence Numbers show irregular gaps.",
        "category": "Log Evasion",
    },
    "RULE_05": {
        "name": "HASH_METADATA_MISMATCH",
        "severity": "HIGH",
        "description": "File hash timeline contradicts SI modification date",
        "explanation": "Content changed after timestamp manipulation, but timestamps were not naturally updated.",
        "category": "Metadata",
    },
    "RULE_06": {
        "name": "EMBEDDED_TIMESTAMP_CONFLICT",
        "severity": "MEDIUM",
        "description": "EXIF/Office/PDF timestamp != SI timestamp",
        "explanation": "Internal metadata (like EXIF or Document Properties) contradicts the NTFS outer metadata ($SI).",
        "category": "Metadata",
    },
    "RULE_07": {
        "name": "ZONE_IDENTIFIER_ABSENT",
        "severity": "MEDIUM",
        "description": "Transfer-origin file missing Zone.Identifier ADS",
        "explanation": "Alternate Data Stream indicating web/external origin (MotW) was deliberately stripped.",
        "category": "Metadata",
    },
    "RULE_08": {
        "name": "VOLUME_SERIAL_MISMATCH",
        "severity": "MEDIUM",
        "description": "Embedded VSN != Device2 VSN",
        "explanation": "File object ID or embedded link indicates it originated on a different NTFS volume.",
        "category": "Cross-Device",
    },
    "RULE_09": {
        "name": "USN_REASON_CODE_GAP",
        "severity": "HIGH",
        "description": "SI shows modification, no USN_REASON_DATA_OVERWRITE",
        "explanation": "Modification not recorded in journal — indicating possible journal evasion tactics.",
        "category": "Log Evasion",
    },
    "RULE_10": {
        "name": "RAPID_METADATA_REWRITE",
        "severity": "MEDIUM",
        "description": "Multiple SI updates within 2-second window",
        "explanation": "Programmatic timestamp manipulation pattern detected (too fast for human editing).",
        "category": "Timestamp",
    },
    "RULE_11": {
        "name": "I30_SLACK_ANOMALY",
        "severity": "LOW",
        "description": "I30 slack space zeroed or wiped",
        "explanation": "Directory slack space deliberately cleared, indicating anti-forensic secure deletion tools.",
        "category": "Metadata",
    },
    "RULE_12": {
        "name": "PARTIAL_MAC_MANIPULATION",
        "severity": "HIGH",
        "description": "Some MAC timestamps changed, others in impossible state",
        "explanation": "Incomplete timestomping attempt left artifact in an invalid or contradictory chronological state.",
        "category": "Timestamp",
    },
    "RULE_13": {
        "name": "ADS_HIDDEN_CONTENT",
        "severity": "MEDIUM",
        "description": "File has undeclared alternate data streams",
        "explanation": "Possible data hiding via ADS without legitimate application association.",
        "category": "Metadata",
    },
    "RULE_14": {
        "name": "MFT_SEQUENCE_ANOMALY",
        "severity": "HIGH",
        "description": "MFT sequence number inconsistent with file age",
        "explanation": "MFT record manipulation or reuse pattern suspicious for the claimed file creation date.",
        "category": "Cross-Device",
    },
    "RULE_15": {
        "name": "CROSS_DEVICE_TRANSFER_SIGNATURE",
        "severity": "CRITICAL",
        "description": "RULE_01 AND RULE_02 AND RULE_03 all TRUE",
        "explanation": "High confidence cross-device transfer with pre-transfer manipulation. File was altered on Device1, moved to Device2, and metadata implies an impossible local timeline.",
        "category": "Cross-Device",
    },
}


def _parse_ts(ts_str: str):
    """Parse an ISO timestamp string to datetime. Returns None on failure."""
    if not ts_str or ts_str == "N/A":
        return None
    try:
        clean = ts_str.replace("Z", "").replace("T", " ")[:19]
        return datetime.strptime(clean, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def evaluate_rules(file_data: Dict[str, Any]) -> List[str]:
    """
    Evaluates a correlated file against all 15 detection rules.
    Returns a list of triggered rule IDs.
    """
    triggered = []

    timestamps = file_data.get("timestamps", {})
    si_c = _parse_ts(timestamps.get("si_created", ""))
    si_m = _parse_ts(timestamps.get("si_modified", ""))
    fn_c = _parse_ts(timestamps.get("fn_created", ""))
    fn_m = _parse_ts(timestamps.get("fn_modified", ""))

    usn_history = file_data.get("usn_history", [])
    logfile = file_data.get("logfile_analysis", {})
    has_basic_info_change = bool(file_data.get("has_basic_info_change", False))
    has_data_overwrite = bool(file_data.get("has_data_overwrite", False))
    usn_event_count = int(file_data.get("usn_event_count", len(usn_history)))

    # ---- R1: SI-FN divergence > 1 hour ----
    if si_m and fn_m:
        delta_hours = abs((si_m - fn_m).total_seconds()) / 3600
        if delta_hours > 1:
            triggered.append("RULE_01")

    # ---- R2: SI modified predates FN created (backdating) ----
    if si_m and fn_c and si_m < fn_c:
        triggered.append("RULE_02")

    # ---- R3: Missing USN history ----
    usn_reasons = [h.get("reason", "") for h in usn_history]
    # Each reason can be pipe-separated (e.g. "FILE_CREATE|CLOSE|BASIC_INFO_CHANGE")
    benign_flags = {"FILE_CREATE", "BASIC_INFO_CHANGE", "CLOSE", "SECURITY_CHANGE",
                    "RENAME_OLD_NAME", "RENAME_NEW_NAME", "OBJECT_ID_CHANGE"}
    all_flags = set()
    for r in usn_reasons:
        all_flags.update(f.strip() for f in r.split("|") if f.strip())
    only_create = (
        len(usn_reasons) > 0
        and all_flags.issubset(benign_flags)
        and "DATA_OVERWRITE" not in all_flags
        and "DATA_EXTEND" not in all_flags
    )
    if only_create and si_m and fn_c and si_m < fn_c:
        triggered.append("RULE_03")

    # ---- R4: LogFile LSN gap ----
    if logfile.get("gap_detected"):
        triggered.append("RULE_04")

    # ---- R5: Hash/metadata mismatch (SI modified but content unchanged) ----
    # If SI claims modification but no DATA_EXTEND or DATA_OVERWRITE in USN
    # and the file has significant size, this indicates metadata-only tampering
    has_data_activity = any(
        "DATA_EXTEND" in r or "DATA_OVERWRITE" in r or "DATA_TRUNCATION" in r
        for r in usn_reasons
    )
    if si_m and fn_c and not has_data_activity and len(usn_reasons) > 0:
        file_size = file_data.get("size_bytes", 0)
        if file_size > 0 and si_m != fn_c:
            triggered.append("RULE_05")

    # ---- R6: Embedded timestamp conflict ----
    # If SI Created is significantly different from FN Created (>30 days)
    # this suggests internal file metadata would conflict with NTFS metadata
    if si_c and fn_c:
        delta_days = abs((si_c - fn_c).days)
        if delta_days > 30:
            triggered.append("RULE_06")

    # ---- R7: Zone.Identifier ADS absent for transferred file ----
    # If file shows cross-device transfer signature (SI predates FN)
    # but has no ADS indicator in USN, the MotW was stripped
    if si_c and fn_c and si_c < fn_c:
        has_ads_event = any("NAMED_DATA_EXTEND" in r or "NAMED_DATA_OVERWRITE" in r for r in usn_reasons)
        if not has_ads_event:
            triggered.append("RULE_07")

    # ---- R8: Volume serial / cross-device origin ----
    # If SI predates FN by a large margin, file originated on another volume
    if si_c and fn_c and (fn_c - si_c).days > 180:
        triggered.append("RULE_08")

    # ---- R9: USN reason code gap (SI shows mod, no DATA_OVERWRITE) ----
    if has_basic_info_change and not has_data_overwrite:
        triggered.append("RULE_09")

    # ---- R10: Rapid metadata rewrite ----
    bic_count = sum(1 for r in usn_reasons if "BASIC_INFO_CHANGE" in r)
    if bic_count >= 2:
        triggered.append("RULE_10")

    # ---- R11: I30 slack anomaly ----
    # If the file's parent path shows directory index manipulation indicators:
    # extremely low USN event count for a file that should have more history
    if usn_event_count <= 1 and si_m and fn_c and si_m < fn_c:
        triggered.append("RULE_11")

    # ---- R12: Partial MAC manipulation (SI-C == SI-M with FN divergence) ----
    if si_c and si_m and si_c == si_m and fn_c:
        if abs((si_c - fn_c).total_seconds()) > 3600:
            triggered.append("RULE_12")

    # ---- R14: MFT sequence anomaly ----
    # If SI claims file is very old but MFT sequence number is low → suspicious
    seq = file_data.get("evidence", {}).get("mft_sequence", 0)
    if si_c and fn_c and (fn_c - si_c).days > 365 and seq and seq < 20:
        triggered.append("RULE_14")

    # ---- R13: ADS hidden content ----
    # If USN has NAMED_DATA events (indicating ADS activity) without
    # corresponding legitimate application patterns
    has_named_data = any("NAMED_DATA" in r for r in usn_reasons)
    has_only_metadata_changes = not has_data_overwrite
    if has_named_data and has_only_metadata_changes:
        triggered.append("RULE_13")

    # ---- R15: Cross-device transfer signature (R1 + R2 + R3) ----
    if all(r in triggered for r in ["RULE_01", "RULE_02", "RULE_03"]):
        triggered.append("RULE_15")

    return triggered
