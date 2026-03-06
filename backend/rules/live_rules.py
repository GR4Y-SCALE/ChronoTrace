"""
ChronoTrace — Live-Only Detection Rules (RULE_16 through RULE_21)
These rules are only possible in live monitoring mode and complement
the existing 15 post-mortem rules from detection_rules.py.
"""

from typing import Dict, Any, List
from datetime import datetime

LIVE_RULES = {
    "RULE_16": {
        "name": "USN_JOURNAL_DELETION",
        "severity": "CRITICAL",
        "description": "USN Journal deletion or reset detected",
        "explanation": (
            "The USN Change Journal was deleted or reset via fsutil. "
            "This destroys the primary audit trail for file system changes."
        ),
        "category": "Journal Destruction",
    },
    "RULE_17": {
        "name": "EVENT_LOG_CLEARING",
        "severity": "CRITICAL",
        "description": "Windows Event Log clearing detected",
        "explanation": (
            "Security or System event log was cleared via wevtutil or PowerShell. "
            "This removes evidence of logon events, privilege use, and audit trails."
        ),
        "category": "Log Clearing",
    },
    "RULE_18": {
        "name": "SHADOW_COPY_DESTRUCTION",
        "severity": "CRITICAL",
        "description": "Volume Shadow Copy deletion detected",
        "explanation": (
            "Volume Shadow Copies were deleted via vssadmin or WMIC. "
            "This destroys previous filesystem snapshots that could be used for recovery."
        ),
        "category": "Shadow Copy Destruction",
    },
    "RULE_19": {
        "name": "PREFETCH_WIPING",
        "severity": "HIGH",
        "description": "Mass deletion in Windows Prefetch directory",
        "explanation": (
            "Files in C:\\Windows\\Prefetch were deleted in bulk. "
            "Prefetch files record evidence of program execution history."
        ),
        "category": "Artifact Destruction",
    },
    "RULE_20": {
        "name": "SETMACE_FINGERPRINT",
        "severity": "CRITICAL",
        "description": "All four $SI timestamps set to identical value",
        "explanation": (
            "All four $STANDARD_INFORMATION timestamps (Created, Modified, Accessed, MFT Modified) "
            "are set to the exact same value. This is a known fingerprint of timestamp manipulation tools "
            "like SetMACE that set all MACE values at once."
        ),
        "category": "Timestamp",
    },
    "RULE_21": {
        "name": "SECURE_DELETE_PATTERN",
        "severity": "HIGH",
        "description": "Overwrite-then-delete pattern detected",
        "explanation": (
            "A file was overwritten (DATA_OVERWRITE) immediately followed by deletion (FILE_DELETE). "
            "This is the signature of secure deletion tools that zero file content before removing it."
        ),
        "category": "Secure Deletion",
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


def evaluate_live_rules(file_data: Dict[str, Any], live_context: Dict[str, Any]) -> List[str]:
    """
    Evaluate live-only rules (RULE_16–RULE_21) against a file data dict
    and additional live context (accumulated USN events, rapid-event flags, etc.)
    Returns a list of triggered rule IDs.
    """
    triggered = []
    timestamps = file_data.get("timestamps", {})
    accumulated = live_context.get("accumulated_events", [])
    mft_data = live_context.get("mft_data", {})

    # ---- RULE_16: USN Journal Deletion ----
    # This is detected at the process level (fsutil usn deletejournal)
    # and also if the journal becomes unavailable during monitoring.
    # The process watcher handles this via TOOL_USN_DELETE.
    # At the file level, we check if accumulated events suddenly stop
    # for a file that was being actively modified.
    # (Handled primarily by ProcessWatcher, placeholder here)

    # ---- RULE_19: Prefetch Wiping ----
    # Check if the file being deleted is in the Prefetch directory
    filename = file_data.get("filename", "")
    reasons_combined = " ".join(e.get("reason", "") for e in accumulated)
    if "FILE_DELETE" in reasons_combined and filename.lower().endswith(".pf"):
        triggered.append("RULE_19")

    # ---- RULE_20: SetMACE Fingerprint ----
    # All four SI timestamps identical (tools set C=M=A=E)
    si_c = timestamps.get("si_created", "N/A")
    si_m = timestamps.get("si_modified", "N/A")
    si_a = timestamps.get("si_accessed", "N/A")
    si_e = timestamps.get("si_mft_modified", "N/A")

    if si_c != "N/A" and si_c == si_m == si_a == si_e:
        # All four are identical — very suspicious, but only flag if FN diverges
        fn_c = timestamps.get("fn_created", "N/A")
        if fn_c != "N/A" and fn_c != si_c:
            triggered.append("RULE_20")

    # ---- RULE_21: Secure Delete Pattern ----
    # DATA_OVERWRITE followed closely by FILE_DELETE for the same file
    has_overwrite_then_delete = False
    for i in range(len(accumulated) - 1):
        cur_reason = accumulated[i].get("reason", "")
        next_reason = accumulated[i + 1].get("reason", "") if i + 1 < len(accumulated) else ""
        if "DATA_OVERWRITE" in cur_reason and "FILE_DELETE" in next_reason:
            has_overwrite_then_delete = True
            break
    if has_overwrite_then_delete:
        triggered.append("RULE_21")

    # ---- RULE_10 enhancement: Rapid BASIC_INFO_CHANGE (live real-time) ----
    if live_context.get("is_rapid", False):
        if "RULE_10" not in file_data.get("_already_triggered", []):
            # RULE_10 is already in the base rules, but live gives us real-time certainty
            pass  # handled by base evaluate_rules

    return triggered
