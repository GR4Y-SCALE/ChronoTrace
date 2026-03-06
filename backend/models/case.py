from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class CaseBase(BaseModel):
    investigator: str
    device_label: str
    notes: Optional[str] = ""

class CaseCreate(CaseBase):
    pass

class Case(CaseBase):
    id: str
    image_hash: str
    status: str = "pending"
    created_at: datetime
    progress: int = 0
    
    class Config:
        from_attributes = True
