import json
from pathlib import Path
from typing import Optional, List

from app.database import SessionLocal, Case, EvidenceItem, ChainOfCustody
from app.hashing import calculate_hashes
from app.services.data_source_service import DataSourceService


class EvidenceService:
    """Handles evidence artifacts (non-image files) + custody logging."""

    @staticmethod
    def add_evidence(
        case_number: str,
        file_path: str,
        collected_by: str,
        notes: str | None = None,
    ) -> EvidenceItem:
        path = Path(file_path).resolve()

        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Reject forensic images — those belong under data sources
        if DataSourceService.is_forensic_image(str(path)):
            raise ValueError(
                "This looks like a forensic image. "
                "Register it as a data source via POST /data-sources/ instead."
            )

        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")

            hash_info = calculate_hashes(str(path))

            evidence = EvidenceItem(
                case_id=case.id,
                original_filename=hash_info["filename"],
                stored_path=str(path),          # <-- keep absolute path
                file_size=hash_info["size"],
                mime_type=hash_info.get("mime_type"),
                sha256_hash=hash_info["sha256"],
                md5_hash=hash_info.get("md5"),
                collected_by=collected_by,
                notes=notes,
                is_consistent=True,
            )
            db.add(evidence)
            db.flush()

            custody_details = {
                "filename": hash_info["filename"],
                "path": str(path),
                "sha256": hash_info["sha256"],
                "size": hash_info["size"],
            }
            if hash_info.get("warning"):
                custody_details["warning"] = hash_info["warning"]

            custody = ChainOfCustody(
                case_id=case.id,
                evidence_id=evidence.id,
                action="evidence_added",
                actor=collected_by,
                details=json.dumps(custody_details),
            )
            db.add(custody)

            db.commit()
            db.refresh(evidence)
            return evidence

        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def list_evidence(case_number: str) -> List[EvidenceItem]:
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")
            return (
                db.query(EvidenceItem)
                .filter(EvidenceItem.case_id == case.id)
                .order_by(EvidenceItem.collected_at.desc())
                .all()
            )
        finally:
            db.close()
