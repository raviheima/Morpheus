from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ---------- Case (unchanged core) ----------

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
    data_source_count: int = 0
    evidence_count: int = 0


# ---------- Data Source ----------

IMAGE_EXTENSIONS = {".e01", ".ex01", ".s01", ".vhd", ".vhdx", ".dd", ".raw", ".img", ".001"}


class DataSourceCreate(BaseModel):
    case_number: str
    file_path: str = Field(..., description="Absolute path to the forensic image")
    collected_by: str
    label: Optional[str] = None
    notes: Optional[str] = None


class DataSourceResponse(BaseModel):
    id: int
    label: Optional[str]
    original_filename: str
    stored_path: str
    file_size: int
    mime_type: Optional[str]
    image_type: Optional[str]
    sha256_hash: str
    md5_hash: Optional[str]
    collected_by: str
    collected_at: datetime
    notes: Optional[str]
    is_consistent: bool
    last_verified_at: Optional[datetime]
    last_warning: Optional[str]

    class Config:
        from_attributes = True


# ---------- Evidence artifact ----------

class EvidenceCreate(BaseModel):
    case_number: str
    file_path: str = Field(..., description="Path to a non-image artifact")
    collected_by: str
    notes: Optional[str] = None


class EvidenceResponse(BaseModel):
    id: int
    original_filename: str
    stored_path: Optional[str]
    file_size: int
    mime_type: Optional[str]
    sha256_hash: str
    md5_hash: Optional[str]
    collected_by: str
    collected_at: datetime
    notes: Optional[str]
    is_consistent: bool
    last_verified_at: Optional[datetime]
    last_warning: Optional[str]

    class Config:
        from_attributes = True


# ---------- Integrity ----------

class IntegrityItemResult(BaseModel):
    kind: str                    # "data_source" | "evidence"
    id: int
    filename: str
    stored_path: Optional[str]
    status: str                  # "ok" | "missing" | "hash_mismatch" | "path_changed"
    message: str
    expected_sha256: Optional[str] = None
    actual_sha256: Optional[str] = None


class IntegrityCheckResponse(BaseModel):
    case_number: str
    checked_at: datetime
    total: int
    ok: int
    warnings: int
    items: List[IntegrityItemResult]
