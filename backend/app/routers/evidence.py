from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.schemas import EvidenceCreate, EvidenceResponse
from app.services.evidence_service import EvidenceService
from app.auth.security import get_current_user, require_roles
from app.auth.models import User
from app.auth.authorization import get_authorized_case
from app.database import SessionLocal
from app.services.audit_service import log_case_action

router = APIRouter(prefix="/evidence", tags=["Evidence"])


@router.post("/", response_model=EvidenceResponse, status_code=201)
def add_evidence(
    payload: EvidenceCreate,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    try:
        with SessionLocal() as db:
            get_authorized_case(db, payload.case_number, current_user)
        evidence = EvidenceService.add_evidence(
            case_number=payload.case_number,
            file_path=payload.file_path,
            collected_by=payload.collected_by or current_user.username,
            notes=payload.notes,
        )
        return evidence
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{case_number}", response_model=List[EvidenceResponse])
def list_evidence(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    try:
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        result = EvidenceService.list_evidence(case_number)
        log_case_action(case_number, "evidence_viewed", current_user.username)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
