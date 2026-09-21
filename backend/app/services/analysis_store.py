import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun  # adjust import path

def create_run(
    db: Session,
    *,
    case_id: int,
    case_number: str,
    data_source_id: Optional[int],
    evidence_path: str,
    created_by: Optional[str] = None,
) -> AnalysisRun:
    job_id = str(uuid.uuid4())
    run = AnalysisRun(
        case_id=case_id,
        case_number=case_number,
        data_source_id=data_source_id,
        evidence_path=evidence_path,
        job_id=job_id,
        status="queued",
        phase="queued",
        progress=0,
        created_by=created_by,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run

def update_progress(
    db: Session,
    job_id: str,
    *,
    status: str = "running",
    phase: Optional[str] = None,
    progress: Optional[int] = None,
    error: Optional[str] = None,
) -> Optional[AnalysisRun]:
    run = db.query(AnalysisRun).filter(AnalysisRun.job_id == job_id).first()
    if not run:
        return None
    run.status = status
    if phase is not None:
        run.phase = phase
    if progress is not None:
        run.progress = progress
    if error is not None:
        run.error = error
    db.commit()
    db.refresh(run)
    return run

def complete_run(
    db: Session,
    job_id: str,
    presentation: dict[str, Any],
    report_pdf_path: Optional[str] = None,
) -> Optional[AnalysisRun]:
    run = db.query(AnalysisRun).filter(AnalysisRun.job_id == job_id).first()
    if not run:
        return None
    run.status = "completed"
    run.phase = "done"
    run.progress = 100
    run.presentation_json = json.dumps(presentation)
    run.report_pdf_path = report_pdf_path
    run.completed_at = datetime.now(timezone.utc)
    run.error = None
    db.commit()
    db.refresh(run)
    return run

def fail_run(db: Session, job_id: str, error: str) -> Optional[AnalysisRun]:
    run = db.query(AnalysisRun).filter(AnalysisRun.job_id == job_id).first()
    if not run:
        return None
    run.status = "failed"
    run.error = error
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run

def get_by_job_id(db: Session, job_id: str) -> Optional[AnalysisRun]:
    return db.query(AnalysisRun).filter(AnalysisRun.job_id == job_id).first()

def latest_for_case(db: Session, case_number: str) -> Optional[AnalysisRun]:
    return (
        db.query(AnalysisRun)
        .filter(AnalysisRun.case_number == case_number)
        .order_by(AnalysisRun.id.desc())
        .first()
    )

def run_to_job_dict(run: AnalysisRun) -> dict:
    presentation = None
    if run.presentation_json:
        try:
            presentation = json.loads(run.presentation_json)
        except json.JSONDecodeError:
            presentation = None
    return {
        "job_id": run.job_id,
        "status": run.status,
        "phase": run.phase,
        "progress": run.progress,
        "error": run.error,
        "case_number": run.case_number,
        "data_source_id": run.data_source_id,
        "evidence_path": run.evidence_path,
        "report_pdf_path": run.report_pdf_path,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "result": presentation,  # UI pickReport() reads this
    }
