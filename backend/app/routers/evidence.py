from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas import EvidenceCreate, EvidenceResponse
from app.services.evidence_service import EvidenceService

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.post("/", response_model=EvidenceResponse, status_code=201)
def add_evidence(payload: EvidenceCreate):
    try:
        evidence = EvidenceService.add_evidence(
            case_number=payload.case_number,
            file_path=payload.file_path,
            collected_by=payload.collected_by,
            notes=payload.notes,
        )
        # Return with evidence_id = md5
        return {
            "evidence_id": evidence.md5_hash,
            "original_filename": evidence.original_filename,
            "file_size": evidence.file_size,
            "mime_type": evidence.mime_type,
            "sha256_hash": evidence.sha256_hash,
            "md5_hash": evidence.md5_hash,
            "collected_by": evidence.collected_by,
            "collected_at": evidence.collected_at,
            "notes": evidence.notes,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{case_number}", response_model=List[EvidenceResponse])
def list_evidence(case_number: str):
    try:
        items = EvidenceService.list_evidence(case_number)
        return [
            {
                "evidence_id": item.md5_hash,
                "original_filename": item.original_filename,
                "file_size": item.file_size,
                "mime_type": item.mime_type,
                "sha256_hash": item.sha256_hash,
                "md5_hash": item.md5_hash,
                "collected_by": item.collected_by,
                "collected_at": item.collected_at,
                "notes": item.notes,
            }
            for item in items
        ]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
