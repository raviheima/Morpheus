from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---------- Case ----------

class CaseCreate(BaseModel):
    case_name: str
    examiner_name: str
    examiner_email: Optional[str] = None
    examiner_notes: Optional[str] = None
    organisation: Optional[str] = None
    description: Optional[str] = None
    case_number: Optional[str] = None


class CaseResponse(BaseModel):
    case_number: str
    case_name: str
    examiner_name: str
    examiner_email: Optional[str]
    examiner_notes: Optional[str]
    organisation: Optional[str]
    description: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CaseDetailsResponse(CaseResponse):
    evidence_count: int


# ---------- Evidence ----------

class EvidenceCreate(BaseModel):
    case_number: str
    file_path: str = Field(..., description="Temporary path to the evidence file")
    collected_by: str
    notes: Optional[str] = None


class EvidenceResponse(BaseModel):
    evidence_id: str          # MD5
    original_filename: str
    file_size: int
    mime_type: Optional[str]
    sha256_hash: str
    md5_hash: str
    collected_by: str
    collected_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


# ---------- Custody ----------

class CustodyLogResponse(BaseModel):
    action: str
    actor: str
    timestamp: datetime
    details: Optional[str]
    evidence_id: Optional[str]   # MD5 if linked to evidence

    class Config:
        from_attributes = True
