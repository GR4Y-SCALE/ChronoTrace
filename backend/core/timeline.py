from typing import List, Dict

class TimelineGenerator:
    def __init__(self, findings: List[Dict]):
        self.findings = findings
        
    def generate(self) -> List[Dict]:
        events = []
        for finding in self.findings:
            ts_comp = finding.get("timestamp_comparison", [])
            
            # Add claimed (fabricated) events from $SI timestamps
            for tc in ts_comp:
                if tc["source"] == "$SI":
                    events.append({
                        "datetime": tc["created"],
                        "date": tc["created"][:10],
                        "time": tc["created"][11:19] if len(tc["created"]) > 10 else "00:00:00",
                        "title": f"Claimed: {finding['filename']}",
                        "description": f"$SI timestamp claims file was created at this time",
                        "risk": finding["risk_level"],
                        "type": "claimed"
                    })
                    if tc["modified"] and tc["modified"] != "N/A":
                        events.append({
                            "datetime": tc["modified"],
                            "date": tc["modified"][:10],
                            "time": tc["modified"][11:19] if len(tc["modified"]) > 10 else "00:00:00",
                            "title": f"Claimed Mod: {finding['filename']}",
                            "description": f"$SI timestamp claims file was modified at this time",
                            "risk": finding["risk_level"],
                            "type": "claimed"
                        })
            
            # Add verified (real) events from $FN timestamps
            for tc in ts_comp:
                if tc["source"] == "$FN":
                    events.append({
                        "datetime": tc["created"],
                        "date": tc["created"][:10],
                        "time": tc["created"][11:19] if len(tc["created"]) > 10 else "00:00:00",
                        "title": f"Verified: {finding['filename']}",
                        "description": f"$FN kernel timestamp - actual arrival on this volume",
                        "risk": "LOW",
                        "type": "verified"
                    })
            
            # Add USN events
            for tc in ts_comp:
                if tc["source"] == "USN":
                    events.append({
                        "datetime": tc["created"],
                        "date": tc["created"][:10],
                        "time": tc["created"][11:19] if len(tc["created"]) > 10 else "00:00:00",
                        "title": f"USN: {finding['filename']}",
                        "description": f"USN Journal FILE_CREATE record",
                        "risk": "LOW",
                        "type": "verified"
                    })

        return sorted(events, key=lambda x: x["datetime"])
