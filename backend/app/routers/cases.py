from fastapi import APIRouter, HTTPException
from typing import List

from app.schemas import CaseCreate, CaseResponse, CaseDetailsResponse
from app.services.case_service import CaseService

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("/", response_model=CaseResponse, status_code=201)
def create_case(payload: CaseCreate):
    try:
        case = CaseService.create_case(
            case_name=payload.case_name,
            examiner_name=payload.examiner_name,
            examiner_email=payload.examiner_email,
            examiner_notes=payload.examiner_notes,
            organisation=payload.organisation,
            description=payload.description,
            case_number=payload.case_number,
        )
        return case
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[CaseResponse])
def list_cases():
    return CaseService.list_cases()


@router.get("/{case_number}", response_model=CaseDetailsResponse)
def get_case(case_number: str):
    result = CaseService.get_case_details(case_number)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")

    case, evidence_count = result
    return {
        **case.__dict__,
        "evidence_count": evidence_count
    }
