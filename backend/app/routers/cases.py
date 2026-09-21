from fastapi import APIRouter, HTTPException, Depends
from typing import List

from app.schemas import CaseCreate, CaseResponse, CaseDetailsResponse
from app.services.case_service import CaseService
from app.auth.security import get_current_user, require_roles
from app.auth.models import User
from app.auth.authorization import get_authorized_case
from app.auth.authorization import DEMO_ORGANISATION
from app.database import SessionLocal
from app.services.audit_service import log_case_action, log_general_action

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("/", response_model=CaseResponse, status_code=201)
def create_case(
    payload: CaseCreate,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    try:
        case = CaseService.create_case(
            case_name=payload.case_name,
            examiner_name=(
                current_user.username
                if current_user.role == "examiner"
                else payload.examiner_name or current_user.username
            ),
            examiner_email=payload.examiner_email,
            examiner_notes=payload.examiner_notes,
            organisation=DEMO_ORGANISATION,
            description=payload.description,
            case_number=payload.case_number,
        )
        return case
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[CaseResponse])
def list_cases(current_user: User = Depends(get_current_user)):
    cases = CaseService.list_cases()
    log_general_action("cases_listed", current_user.username, {"count": len(cases)})
    if current_user.role == "admin":
        return cases
    return [case for case in cases if case.organisation == DEMO_ORGANISATION]


@router.get("/{case_number}", response_model=CaseDetailsResponse)
def get_case(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        get_authorized_case(db, case_number, current_user)
    result = CaseService.get_case_details(case_number)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")

    case, evidence_count = result
    log_case_action(case_number, "case_viewed", current_user.username)
    return {
        **{k: v for k, v in case.__dict__.items() if not k.startswith("_")},
        "evidence_count": evidence_count,
    }


@router.post("/{case_number}/close", response_model=CaseResponse)
def close_case(
    case_number: str,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    try:
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        return CaseService.close_case(case_number, closed_by=current_user.username)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{case_number}/reopen", response_model=CaseResponse)
def reopen_case(
    case_number: str,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    try:
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        return CaseService.reopen_case(
            case_number, reopened_by=current_user.username
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.delete("/{case_number}")
def delete_case(
    case_number: str,
    current_user: User = Depends(require_roles("admin")),
):
    """Soft-delete. Chain of custody is kept."""
    try:
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        CaseService.delete_case(case_number, deleted_by=current_user.username)
        return {"ok": True, "case_number": case_number, "status": "deleted"}
    except ValueError as e:
        raise HTTPException(404, str(e))
