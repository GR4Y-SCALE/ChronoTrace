import asyncio
from typing import Dict, Any, List
from rules.detection_rules import evaluate_rules, RULES
import uuid

class Detector:
    def __init__(self, correlated_files: List[Dict]):
        self.correlated_files = correlated_files
        
    async def analyze(self, callback=None) -> List[Dict]:
        """
        Runs the logic engine against the correlated files to detect specific anti-forensic patterns.
        """
        if callback: await callback("⏳ Anomaly detection — applying 15 heuristic rules...")
        await asyncio.sleep(0.3)
        
        findings = []
        
        for file in self.correlated_files:
            triggered_rules = evaluate_rules(file)
            if triggered_rules:
                # Calculate Severity and Risk
                highest_severity = "LOW"
                confidence = 50
                
                severities = [RULES[r]["severity"] for r in triggered_rules]
                if "CRITICAL" in severities:
                    highest_severity = "CRITICAL"
                    confidence = 94 if len(triggered_rules) > 3 else 88
                elif "HIGH" in severities:
                    highest_severity = "HIGH"
                    confidence = 87 if len(triggered_rules) >= 3 else 80
                elif "MEDIUM" in severities:
                    highest_severity = "MEDIUM"
                    confidence = 71
                
                finding = {
                    "id": str(uuid.uuid4()),
                    "filename": file["filename"],
                    "risk_level": highest_severity,
                    "confidence_score": confidence,
                    "size_bytes": file["size_bytes"],
                    "mft_entry": file["mft_entry"],
                    "rules_triggered": triggered_rules,
                    "evidence": file["evidence"],
                    "court_explanation": self._generate_court_explanation(file["filename"], triggered_rules),
                    "timestamp_comparison": self._format_timestamp_comparison(file)
                }
                findings.append(finding)
                
        if callback: await callback(f"✅ Anomaly detection complete — {len(findings)} files flagged")
        return findings

    def _format_timestamp_comparison(self, file_data):
        comps = []
        ts = file_data.get("timestamps", {})
        
        if ts.get("si_created"):
            comps.append({"source": "$SI", "created": ts.get("si_created")[:19], "modified": ts.get("si_modified")[:19], "status": "Sus" if ts.get("si_created") < ts.get("fn_created", "") else "OK"})
        if ts.get("fn_created"):
            comps.append({"source": "$FN", "created": ts.get("fn_created")[:19], "modified": ts.get("fn_modified")[:19], "status": "OK"})
            
        usn = file_data.get("usn_history", [])
        if usn:
            comps.append({"source": "USN", "created": usn[0]["timestamp"][:19], "modified": usn[-1]["timestamp"][:19], "status": "OK"})
            
        if ts.get("exif_created"):
            comps.append({"source": "EXIF", "created": ts.get("exif_created")[:19], "modified": "N/A", "status": "Sus" if ts.get("exif_created") != ts.get("si_created") else "OK"})
            
        return comps
        
    def _generate_court_explanation(self, filename, rules):
        if "RULE_15" in rules or "RULE_02" in rules:
            return f"{filename} shows $SI timestamps that predate its $FN arrival timestamp on this volume. This is forensically impossible under normal usage. The file was almost certainly timestamp-manipulated before transfer to this device."
        elif "RULE_01" in rules:
            return f"{filename} has a massive divergence between its $SI and $FN timestamps, strongly indicating anti-forensic timestomping tools were used."
        elif "RULE_06" in rules:
            return f"{filename} contains embedded internal metadata (EXIF/OLE) that contradicts the NTFS timestamps, indicating the outer filesystem dates were altered."
        return f"Suspicious anti-forensic artifacts detected for {filename} requiring manual review."
