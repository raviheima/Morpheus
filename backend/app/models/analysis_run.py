from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False, index=True)
    case_number = Column(String(64), nullable=False, index=True)
    data_source_id = Column(Integer, nullable=True, index=True)
    evidence_path = Column(String(1024), nullable=True)
    job_id = Column(String(64), unique=True, index=True)
    status = Column(String(32), default="queued")  # queued|running|completed|failed
    phase = Column(String(128), nullable=True)
    progress = Column(Integer, default=0)
    error = Column(Text, nullable=True)
    presentation_json = Column(Text, nullable=True)  # full presentation JSON
    report_pdf_path = Column(String(1024), nullable=True)
    created_by = Column(String(128), nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
