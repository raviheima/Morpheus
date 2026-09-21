from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel
from typing import Optional, Any
from pathlib import Path
import json
import uuid

import pytsk3
import pyewf

from app.auth.security import get_current_user, require_roles
from app.auth.models import User
from app.auth.authorization import get_authorized_case
from app.analysis.orchestrator import AnalysisOrchestrator
from app.analysis.artifacts import ArtifactCollector
from app.analysis.artifact_exporter import ArtifactExporter
from app.analysis.timeline import TimelineBuilder
from app.analysis.identifier import EWFImgInfo, DataSourceIdentifier
from app.analysis.presentation import build_presentation
from app.database import SessionLocal, Case, ChainOfCustody, DataSource
from app.services import analysis_store
from app.services.ai_summary import generate_summary, is_configured as ai_is_configured
from app.services.audit_service import log_case_action, log_general_action

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    evidence_path: str
    case_number: Optional[str] = None
    data_source_id: Optional[int] = None
    export_artifacts: bool = True
    build_timeline: bool = False
    output_dir: Optional[str] = None


class AnalyzeResponse(BaseModel):
    job_id: str
    status: str
    message: str


class ExportFileRequest(BaseModel):
    evidence_path: str
    file_path: str
    case_number: str
    volume_start_sector: Optional[int] = None


class AiSummaryRequest(BaseModel):
    case_number: str
    presentation: Optional[dict] = None  # if omitted, load latest from DB


_jobs: dict = {}


def _open_image(path: str):
    p = Path(path)
    if p.name.lower().endswith((".e01", ".ex01", ".s01")):
        filenames = pyewf.glob(str(p))
        handle = pyewf.handle()
        handle.open(filenames)
        return EWFImgInfo(handle)
    return pytsk3.Img_Info(str(p))


def _read_file_from_image(
    evidence_path: str,
    file_path: str,
    volume_start_sector: Optional[int] = None,
) -> bytes:
    img_info = _open_image(evidence_path)
    if volume_start_sector is None:
        ident = DataSourceIdentifier().analyze(evidence_path)
        vol = next(
            (
                v
                for v in ident.get("volumes", [])
                if v.get("filesystem") not in (None, "Unknown")
            ),
            None,
        )
        if not vol:
            raise HTTPException(400, "No usable volume found in image")
        volume_start_sector = vol["start_sector"]
    offset = volume_start_sector * 512
    fs = pytsk3.FS_Info(img_info, offset=offset)
    tsk_path = file_path.replace("\\", "/")
    if ":" in tsk_path:
        tsk_path = tsk_path.split(":", 1)[-1]
    if not tsk_path.startswith("/"):
        tsk_path = "/" + tsk_path
    try:
        file_obj = fs.open(path=tsk_path)
    except Exception as exc:
        raise HTTPException(404, f"File not found in image: {file_path} ({exc})")
    size = file_obj.info.meta.size or 0
    if size > 100 * 1024 * 1024:
        raise HTTPException(413, "File too large (>100 MB)")
    return file_obj.read_random(0, size)


def _log_custody(case_number: Optional[str], action: str, actor: str, details: dict):
    if not case_number:
        return
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.case_number == case_number).first()
        if not case:
            return
        db.add(
            ChainOfCustody(
                case_id=case.id,
                action=action,
                actor=actor,
                details=json.dumps(details, default=str),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.post("/run", response_model=AnalyzeResponse)
def start_analysis(
    req: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    if not Path(req.evidence_path).exists():
        raise HTTPException(404, "Evidence file not found")

    case_number = req.case_number
    case_id = None
    ds_id = req.data_source_id

    db = SessionLocal()
    try:
        if case_number:
            case = get_authorized_case(db, case_number, current_user)
            case_id = case.id
        elif ds_id is not None:
            data_source = db.query(DataSource).filter(DataSource.id == ds_id).first()
            if not data_source:
                raise HTTPException(404, "Data source not found")
            get_authorized_case(db, data_source.case_id, current_user)
        if ds_id is None and case_id is not None:
            ds = (
                db.query(DataSource)
                .filter(DataSource.case_id == case_id)
                .order_by(DataSource.id.desc())
                .first()
            )
            if ds:
                ds_id = ds.id
        run = None
        if case_id and case_number:
            run = analysis_store.create_run(
                db,
                case_id=case_id,
                case_number=case_number,
                data_source_id=ds_id,
                evidence_path=req.evidence_path,
                created_by=current_user.username,
            )
            job_id = run.job_id
        else:
            job_id = str(uuid.uuid4())
    finally:
        db.close()

    output_dir = req.output_dir or f"/tmp/morpheus_jobs/{job_id}"
    _jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "phase": "queued",
        "user": current_user.username,
        "result": None,
        "error": None,
        "case_number": case_number,
    }

    _log_custody(
        case_number,
        "analysis_started",
        current_user.username,
        {"evidence_path": req.evidence_path, "job_id": job_id},
    )

    background_tasks.add_task(
        _run_analysis_job,
        job_id,
        req.evidence_path,
        output_dir,
        req.export_artifacts,
        req.build_timeline,
        case_number,
        current_user.username,
    )
    return AnalyzeResponse(
        job_id=job_id,
        status="queued",
        message="Analysis started. Results will be stored when complete.",
    )


@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    job = _jobs.get(job_id)
    if job:
        if job.get("case_number"):
            with SessionLocal() as db:
                get_authorized_case(db, job["case_number"], current_user)
        elif job.get("user") != current_user.username and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="You are not authorized to access this job")
        if job.get("case_number"):
            log_case_action(job["case_number"], "analysis_status_viewed", current_user.username)
        else:
            log_general_action("analysis_status_viewed", current_user.username, {"job_id": job_id})
        return job
    # fall back to SQLite
    db = SessionLocal()
    try:
        run = analysis_store.get_by_job_id(db, job_id)
        if not run:
            raise HTTPException(404, "Job not found")
        get_authorized_case(db, run.case_number, current_user)
        log_case_action(run.case_number, "analysis_status_viewed", current_user.username)
        return analysis_store.run_to_job_dict(run)
    finally:
        db.close()


@router.get("/case/{case_number}/latest")
def latest_analysis_for_case(
    case_number: str,
    current_user: User = Depends(get_current_user),
):
    """Return the latest stored analysis for a case (no need to re-run)."""
    db = SessionLocal()
    try:
        get_authorized_case(db, case_number, current_user)
        run = analysis_store.latest_for_case(db, case_number)
        if not run:
            log_case_action(case_number, "analysis_viewed", current_user.username)
            return {"status": "none", "result": None, "job_id": None}
        log_case_action(case_number, "analysis_viewed", current_user.username)
        return analysis_store.run_to_job_dict(run)
    finally:
        db.close()


@router.post("/ai-summary")
def ai_summary(
    req: AiSummaryRequest,
    current_user: User = Depends(get_current_user),
):
    """Generate a plain-language summary for judges (needs MORPHEUS_AI_API_KEY)."""
    presentation = req.presentation
    if not presentation:
        db = SessionLocal()
        try:
            get_authorized_case(db, req.case_number, current_user)
            run = analysis_store.latest_for_case(db, req.case_number)
            if not run or not run.presentation_json:
                raise HTTPException(
                    400,
                    "No stored analysis for this case. Run analysis first.",
                )
            presentation = json.loads(run.presentation_json)
        finally:
            db.close()

    case_meta = {"case_number": req.case_number}
    db = SessionLocal()
    try:
        case = get_authorized_case(db, req.case_number, current_user)
        case_meta["case_name"] = case.case_name
        case_meta["examiner_name"] = case.examiner_name
    finally:
        db.close()

    result = generate_summary(presentation, case_meta)
    if result.get("ok") and result.get("summary"):
        _log_custody(
            req.case_number,
            "ai_summary_generated",
            current_user.username,
            {"model": result.get("model"), "chars": len(result["summary"])},
        )
    log_case_action(req.case_number, "ai_summary_requested", current_user.username)
    return {
        **result,
        "ai_configured": ai_is_configured(),
    }


@router.get("/ai-status")
def ai_status(current_user: User = Depends(get_current_user)):
    return {"ai_configured": ai_is_configured()}


@router.post("/export-file")
def export_single_file(
    req: ExportFileRequest,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    """Extract one specific file from a forensic image and return its bytes."""
    db = SessionLocal()
    try:
        get_authorized_case(db, req.case_number, current_user)
    finally:
        db.close()
    if not Path(req.evidence_path).exists():
        raise HTTPException(404, "Evidence file not found on disk")
    data = _read_file_from_image(
        evidence_path=req.evidence_path,
        file_path=req.file_path,
        volume_start_sector=req.volume_start_sector,
    )
    log_case_action(
        req.case_number,
        "file_extracted",
        current_user.username,
        {"file_path": req.file_path},
    )
    name = req.file_path.replace("\\", "/").rsplit("/", 1)[-1] or "exported.bin"
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Content-Length": str(len(data)),
        },
    )


def _run_analysis_job(
    job_id: str,
    evidence_path: str,
    output_dir: str,
    export_artifacts: bool,
    build_timeline: bool,
    case_number: Optional[str] = None,
    actor: str = "system",
):
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["progress"] = 5
    _jobs[job_id]["phase"] = "identifying"

    db = SessionLocal()
    try:
        analysis_store.update_progress(
            db, job_id, status="running", phase="identifying", progress=5
        )
    finally:
        db.close()

    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        _jobs[job_id]["phase"] = "scanning"
        _jobs[job_id]["progress"] = 15
        db = SessionLocal()
        try:
            analysis_store.update_progress(
                db, job_id, status="running", phase="scanning", progress=15
            )
        finally:
            db.close()

        orchestrator = AnalysisOrchestrator()
        report = orchestrator.analyze(evidence_path)

        _jobs[job_id]["phase"] = "collecting_artifacts"
        _jobs[job_id]["progress"] = 75

        collector = ArtifactCollector()
        artifacts = collector.collect(report)

        _jobs[job_id]["phase"] = "building_presentation"
        _jobs[job_id]["progress"] = 85

        result = build_presentation(report)
        if not isinstance(result, dict):
            result = {}
        result["artifact_count"] = len(artifacts)
        result["artifacts_preview"] = artifacts[:50]

        if export_artifacts:
            _jobs[job_id]["phase"] = "exporting_artifacts"
            _jobs[job_id]["progress"] = 90
            exporter = ArtifactExporter()
            manifest_path = Path(output_dir) / "artifacts.json"
            exporter.export_json(artifacts, manifest_path)
            result["manifest_path"] = str(manifest_path)

        if build_timeline:
            _jobs[job_id]["phase"] = "timeline"
            tl = TimelineBuilder()
            tl_path = Path(output_dir) / "timeline_from_artifacts.jsonl"
            tl.build_from_artifacts(artifacts, tl_path)
            result["timeline_path"] = str(tl_path)

        try:
            from app.analysis.report import export_report_json

            pres_path = Path(output_dir) / "analysis_report_presentation.json"
            export_report_json(report, str(pres_path), presentation_only=True)
            result["presentation_path"] = str(pres_path)
        except Exception:
            pass

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["phase"] = "done"
        _jobs[job_id]["result"] = result

        db = SessionLocal()
        try:
            analysis_store.complete_run(db, job_id, presentation=result)
        finally:
            db.close()

        _log_custody(
            case_number,
            "analysis_completed",
            actor,
            {
                "job_id": job_id,
                "evidence_path": evidence_path,
                "files_scanned": (result.get("case_summary") or {}).get(
                    "total_files_scanned"
                ),
            },
        )
    except Exception as exc:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["phase"] = "failed"
        db = SessionLocal()
        try:
            analysis_store.fail_run(db, job_id, str(exc))
        finally:
            db.close()
        _log_custody(
            case_number,
            "analysis_failed",
            actor,
            {"job_id": job_id, "error": str(exc)[:500]},
        )
