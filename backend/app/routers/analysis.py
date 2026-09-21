from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
import json
import uuid

import pytsk3
import pyewf

from app.auth.security import get_current_user, require_roles
from app.auth.models import User
from app.analysis.orchestrator import AnalysisOrchestrator
from app.analysis.artifacts import ArtifactCollector
from app.analysis.artifact_exporter import ArtifactExporter
from app.analysis.timeline import TimelineBuilder
from app.analysis.identifier import EWFImgInfo, DataSourceIdentifier
from app.analysis.presentation import build_presentation

router = APIRouter(prefix="/analysis", tags=["analysis"])

class AnalyzeRequest(BaseModel):
    evidence_path: str
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
    volume_start_sector: Optional[int] = None

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

@router.post("/run", response_model=AnalyzeResponse)
def start_analysis(
    req: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    if not Path(req.evidence_path).exists():
        raise HTTPException(404, "Evidence file not found")
    job_id = str(uuid.uuid4())
    output_dir = req.output_dir or f"/tmp/morpheus_jobs/{job_id}"
    _jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "phase": "queued",
        "user": current_user.username,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(
        _run_analysis_job,
        job_id,
        req.evidence_path,
        output_dir,
        req.export_artifacts,
        req.build_timeline,
    )
    return AnalyzeResponse(
        job_id=job_id,
        status="queued",
        message="Analysis started",
    )

@router.get("/jobs/{job_id}")
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job

@router.post("/export-file")
def export_single_file(
    req: ExportFileRequest,
    current_user: User = Depends(require_roles("admin", "examiner")),
):
    """Extract one specific file from a forensic image and return its bytes."""
    if not Path(req.evidence_path).exists():
        raise HTTPException(404, "Evidence file not found on disk")
    data = _read_file_from_image(
        evidence_path=req.evidence_path,
        file_path=req.file_path,
        volume_start_sector=req.volume_start_sector,
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
):
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["progress"] = 5
    _jobs[job_id]["phase"] = "identifying"
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        _jobs[job_id]["phase"] = "scanning"
        _jobs[job_id]["progress"] = 15

        orchestrator = AnalysisOrchestrator()
        report = orchestrator.analyze(evidence_path)

        _jobs[job_id]["phase"] = "collecting_artifacts"
        _jobs[job_id]["progress"] = 75

        collector = ArtifactCollector()
        artifacts = collector.collect(report)

        _jobs[job_id]["phase"] = "building_presentation"
        _jobs[job_id]["progress"] = 85

        # Same presentation pipeline as test_orchestrator (via presentation.py)
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

        # Optional: also write presentation JSON next to job output
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
    except Exception as exc:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["phase"] = "failed"
