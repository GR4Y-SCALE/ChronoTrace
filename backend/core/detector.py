"""ChronoTrace — Detection
Runs deterministic rule-based detection on correlated files.
"""

import asyncio
import uuid
from typing import Dict, List

from rules.detection_rules import evaluate_rules, RULES


# ---------- Main Detector ----------

class Detector:
    def __init__(self, correlated_files: List[Dict]):
        self.correlated_files = correlated_files

    async def analyze(self, callback=None) -> List[Dict]:
        if callback:
            await callback("⏳ Anomaly detection — applying deterministic rules...")
        await asyncio.sleep(0.2)

        findings = []

        for file_data in self.correlated_files:
            triggered_rules = evaluate_rules(file_data)
            if not triggered_rules:
                continue

            highest_severity = self._compute_severity(triggered_rules)
            confidence = self._compute_confidence(triggered_rules, highest_severity)

            finding = {
                "id": str(uuid.uuid4()),
                "filename": file_data["filename"],
                "parent_path": file_data.get("parent_path", ""),
                "risk_level": highest_severity,
                "confidence_score": confidence,
                "size_bytes": file_data["size_bytes"],
                "mft_entry": file_data["mft_entry"],
                "rules_triggered": triggered_rules,
                "evidence": file_data["evidence"],
                "logfile_analysis": file_data.get("logfile_analysis", {}),
                "usn_analysis": file_data.get("usn_analysis", {}),
                "court_explanation": self._generate_court_explanation(
                    file_data["filename"], triggered_rules),
                "timestamp_comparison": self._format_timestamp_comparison(file_data),
            }
            findings.append(finding)

        if callback:
            await callback(f"✅ Anomaly detection complete — {len(findings)} files flagged")
        return findings

    # ----- helpers -----

    def _compute_severity(self, rules: List[str]) -> str:
        severities = [RULES[r]["severity"] for r in rules if r in RULES]
        if "CRITICAL" in severities:
            return "CRITICAL"
        if "HIGH" in severities:
            return "HIGH"
        if "MEDIUM" in severities:
            return "MEDIUM"
        return "LOW"

    def _compute_confidence(self, rules: List[str], highest_severity: str) -> int:
        severity_bonus = {
            "CRITICAL": 30,
            "HIGH": 22,
            "MEDIUM": 14,
            "LOW": 8,
        }
        score = 35 + (len(rules) * 6) + severity_bonus.get(highest_severity, 8)
        return min(99, score)

    def _format_timestamp_comparison(self, file_data):
        comps = []
        ts = file_data.get("timestamps", {})

        if ts.get("si_created") and ts["si_created"] != "N/A":
            si_c = ts.get("si_created", "")[:19]
            si_m = ts.get("si_modified", "")[:19]
            fn_c = ts.get("fn_created", "")[:19]
            is_sus = si_c < fn_c if fn_c else False
            comps.append({"source": "$SI", "created": si_c, "modified": si_m, "status": "Sus" if is_sus else "OK"})

        if ts.get("fn_created") and ts["fn_created"] != "N/A":
            comps.append({
                "source": "$FN",
                "created": ts.get("fn_created", "")[:19],
                "modified": ts.get("fn_modified", "")[:19],
                "status": "OK"
            })

        usn = file_data.get("usn_history", [])
        if usn:
            first_ts = usn[0].get("timestamp", "")[:19]
            last_ts = usn[-1].get("timestamp", "")[:19]
            comps.append({"source": "USN", "created": first_ts, "modified": last_ts, "status": "OK"})

        return comps

    def _generate_court_explanation(self, filename: str, rules: List[str]) -> str:

        if "RULE_15" in rules:
            return (
                f"{filename} shows $SI timestamps that predate its $FN arrival timestamp on this volume. "
                f"This is forensically impossible under normal NTFS operation. The file was timestamp-manipulated "
                f"before transfer to this device."
            )
        if "RULE_02" in rules:
            return (
                f"{filename} has $SI timestamps claiming the file existed before the $FN kernel timestamp shows "
                f"it arrived on this volume — a definitive indicator of timestomping."
            )
        if "RULE_01" in rules:
            return (
                f"{filename} has a massive divergence between $SI and $FN timestamps, strongly indicating "
                f"anti-forensic timestomping tools were used."
            )
        return f"Suspicious anti-forensic artifacts detected for {filename}."
