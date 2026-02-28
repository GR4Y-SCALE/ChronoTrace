from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class EvidenceReference(BaseModel):
    usn_record_id: Optional[str] = None
    logfile_lsn: Optional[str] = None
    mft_sequence: Optional[int] = None
    cluster: Optional[str] = None

class DateComparison(BaseModel):
    source: str
    created: Optional[str]
    modified: Optional[str]
    status: str

class Finding(BaseModel):
    id: str
    case_id: str
    filename: str
    risk_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    confidence_score: int
    size_bytes: int
    mft_entry: int
    
    timestamp_comparison: List[DateComparison]
    rules_triggered: List[str]
    evidence: EvidenceReference
    court_explanation: str
