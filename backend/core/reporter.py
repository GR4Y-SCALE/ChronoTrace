import json
from models.report import FullReport, SummaryStats
from models.finding import Finding

class Reporter:
    def __init__(self, case, findings, timeline):
        self.case = case
        self.findings = findings
        self.timeline = timeline
        
    def generate_report_object(self) -> FullReport:
        critical = sum(1 for f in self.findings if f["risk_level"] == "CRITICAL")
        high = sum(1 for f in self.findings if f["risk_level"] == "HIGH")
        medium = sum(1 for f in self.findings if f["risk_level"] == "MEDIUM")
        low = sum(1 for f in self.findings if f["risk_level"] == "LOW")
        
        score = 0
        if critical > 0: score = 82
        elif high > 0: score = 65
        elif medium > 0: score = 40
        else: score = 10
            
        summary = SummaryStats(
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            overall_risk_score=score,
            overall_risk_label="CRITICAL" if score > 80 else "HIGH" if score > 60 else "MEDIUM"
        )
        
        # Hydrate pydantic models
        parsed_findings = [Finding(**f, case_id=self.case.id) for f in self.findings]
        
        report = FullReport(
            case_info=self.case,
            summary=summary,
            findings=parsed_findings,
            timeline_events=self.timeline
        )
        return report
