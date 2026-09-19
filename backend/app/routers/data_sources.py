from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from typing import List
from fastapi.responses import FileResponse
from app.services.certificate_service import CertificateService
import tempfile
from app.schemas import DataSourceCreate, DataSourceResponse, IntegrityCheckResponse
from app.services.data_source_service import DataSourceService
from app.services.integrity_service import IntegrityService
from app.auth.security import require_roles, get_current_user
from app.auth.models import User

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


@router.post("/", response_model=DataSourceResponse, status_code=201)
def add_data_source(
    payload: DataSourceCreate,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    try:
        ds = DataSourceService.add_data_source(
            case_number=payload.case_number,
            file_path=payload.file_path,
            collected_by=payload.collected_by or current_user.username,
            label=payload.label,
            notes=payload.notes,
        )
        return ds
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{case_number}", response_model=List[DataSourceResponse])
def list_data_sources(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return DataSourceService.list_data_sources(case_number)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{case_number}/integrity-check", response_model=IntegrityCheckResponse)
def check_integrity(
    case_number: str,
    current_user: User = Depends(require_roles("admin", "examiner", "viewer")),
):
    """
    Re-hash all data sources + evidence files for the case.
    Returns per-file status: ok | missing | hash_mismatch.
    """
    try:
        return IntegrityService.check_case(case_number, actor=current_user.username)
    except ValueError as e:
        raise HTTPException(404, str(e))



@router.get("/{case_number}/certificate.pdf")
def download_certificate_pdf(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    try:
        tmp = Path(tempfile.gettempdir()) / f"morpheus_cert_{case_number}.pdf"
        CertificateService.write_pdf(case_number, tmp)
        return FileResponse(
            tmp,
            media_type="application/pdf",
            filename=f"integrity_certificate_{case_number}.pdf",
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{case_number}/custody-report")
def custody_report_json(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    try:
        return CertificateService.build_certificate_data(case_number)
    except ValueError as e:
        raise HTTPException(404, str(e))
