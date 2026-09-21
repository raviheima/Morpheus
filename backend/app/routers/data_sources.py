from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path
from typing import List
from fastapi.responses import FileResponse
from app.services.certificate_service import CertificateService
import tempfile
from app.schemas import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourcePathUpdate,
    IntegrityCheckResponse,
)
from app.services.data_source_service import DataSourceService, DuplicateDataSourceError
from app.services.integrity_service import IntegrityService
from app.auth.security import require_roles, get_current_user
from app.auth.models import User
from app.auth.authorization import get_authorized_case, get_authorized_data_source
from app.database import SessionLocal, ChainOfCustody, Case, AuditLog
import json
from datetime import datetime, timezone
from app.services.audit_service import log_case_action

router = APIRouter(prefix="/data-sources", tags=["Data Sources"])


@router.post("/", response_model=DataSourceResponse, status_code=201)
def add_data_source(
    payload: DataSourceCreate,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    try:
        with SessionLocal() as db:
            get_authorized_case(db, payload.case_number, current_user)
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
    except DuplicateDataSourceError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(e),
                "duplicate": True,
                "existing_data_source_id": e.existing_id,
                "existing_path": e.existing_path,
                "existing_filename": e.existing_filename,
                "sha256": e.sha256,
                "path_update_endpoint": f"/data-sources/by-id/{e.existing_id}/path",
            },
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/{case_number}", response_model=List[DataSourceResponse])
def list_data_sources(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    try:
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        result = DataSourceService.list_data_sources(case_number)
        log_case_action(case_number, "data_sources_viewed", current_user.username)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.patch("/by-id/{ds_id}/path", response_model=DataSourceResponse)
def update_data_source_path(
    ds_id: int,
    payload: DataSourcePathUpdate,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    """
    Update path when the evidence file moved but content is the same.
    SHA-256 must match the registered fingerprint or the update is rejected.
    """
    try:
        with SessionLocal() as db:
            get_authorized_data_source(db, ds_id, current_user)
        return DataSourceService.update_path(
            ds_id=ds_id,
            new_path=payload.new_path,
            actor=current_user.username,
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))


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
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        return IntegrityService.check_case(case_number, actor=current_user.username)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{case_number}/report.pdf")
def download_case_report_pdf(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    """Full case report: integrity + analysis findings + chain of custody."""
    try:
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        tmp = Path(tempfile.gettempdir()) / f"morpheus_report_{case_number}.pdf"
        CertificateService.write_full_report_pdf(case_number, tmp)

        # custody: report downloaded
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if case:
                db.add(
                    ChainOfCustody(
                        case_id=case.id,
                        action="report_downloaded",
                        actor=current_user.username,
                        details=json.dumps(
                            {
                                "format": "pdf",
                                "note": "Case report (findings + integrity + custody)",
                            }
                        ),
                    )
                )
                db.commit()
        finally:
            db.close()

        return FileResponse(
            tmp,
            media_type="application/pdf",
            filename=f"morpheus_report_{case_number}.pdf",
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


# Back-compat alias — same full report (no longer a separate "certificate")
@router.get("/{case_number}/certificate.pdf")
def download_certificate_pdf_alias(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    return download_case_report_pdf(case_number, current_user)


@router.get("/{case_number}/custody-report")
def custody_report_json(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    try:
        with SessionLocal() as db:
            get_authorized_case(db, case_number, current_user)
        result = CertificateService.build_certificate_data(case_number)
        log_case_action(case_number, "custody_viewed", current_user.username)
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/{case_number}/audit-report")
def audit_report(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    with SessionLocal() as db:
        get_authorized_case(db, case_number, current_user)
        entries = (
            db.query(AuditLog)
            .order_by(AuditLog.timestamp.desc())
            .limit(500)
            .all()
        )
        return [
            {
                "id": entry.id,
                "case_id": entry.case_id,
                "action": entry.action,
                "actor": entry.actor,
                "timestamp": entry.timestamp,
                "details": entry.details,
            }
            for entry in entries
        ]


@router.get("/{case_number}/extractions")
def extraction_log(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    """Return the files extracted from a case, newest first."""
    with SessionLocal() as db:
        case = get_authorized_case(db, case_number, current_user)
        entries = (
            db.query(ChainOfCustody)
            .filter(
                ChainOfCustody.case_id == case.id,
                ChainOfCustody.action == "file_extracted",
            )
            .order_by(ChainOfCustody.timestamp.desc(), ChainOfCustody.id.desc())
            .all()
        )
        result = []
        for entry in entries:
            details = {}
            try:
                details = json.loads(entry.details or "{}")
            except json.JSONDecodeError:
                pass
            result.append(
                {
                    "id": entry.id,
                    "actor": entry.actor,
                    "timestamp": entry.timestamp,
                    "file_path": details.get("file_path", ""),
                }
            )
        return result
