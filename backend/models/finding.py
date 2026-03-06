from pydantic import BaseModel
from typing import Optional, List, Dict, Any

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

class LogfileTransaction(BaseModel):
    lsn: str
    operation: str
    timestamp: str
    status: str

class LogfileAnalysis(BaseModel):
    transactions: List[LogfileTransaction] = []
    gap_detected: bool = False
    gap_detail: str = ""

class UsnAnalysisEntry(BaseModel):
    reason: Optional[str] = None
    timestamp: Optional[str] = None
    usn_seq: Optional[int] = None
    detail: Optional[str] = None

class UsnAnalysis(BaseModel):
    present: List[Dict[str, Any]] = []
    missing: List[Dict[str, Any]] = []
    conclusion: str = ""

class Finding(BaseModel):
    id: str
    case_id: str
    filename: str
    parent_path: str = ""
    risk_level: str  # CRITICAL, HIGH, MEDIUM, LOW
    confidence_score: int
    size_bytes: int
    mft_entry: int
    
    timestamp_comparison: List[DateComparison]
    rules_triggered: List[str]
    evidence: EvidenceReference
    court_explanation: str

    logfile_analysis: LogfileAnalysis = LogfileAnalysis()
    usn_analysis: UsnAnalysis = UsnAnalysis()
