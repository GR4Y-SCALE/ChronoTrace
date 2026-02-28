from pydantic import BaseModel
from typing import List, Dict, Any
from .finding import Finding
from .case import Case

class SummaryStats(BaseModel):
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    overall_risk_score: int = 0
    overall_risk_label: str = "LOW"
    anomaly_distribution: Dict[str, int] = {
        "Timestamp": 0,
        "Log Evasion": 0,
        "Cross-Device": 0,
        "Metadata": 0
    }
    rules_triggered: Dict[str, int] = {}

class FullReport(BaseModel):
    case_info: Case
    summary: SummaryStats
    findings: List[Finding]
    timeline_events: List[Dict[str, Any]]
