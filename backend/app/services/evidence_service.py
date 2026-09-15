import json
from typing import Optional, List

from app.database import SessionLocal, Case, EvidenceItem, ChainOfCustody
from app.hashing import calculate_hashes


class EvidenceService:
    """Handles evidence addition and retrieval + custody logging."""
    @staticmethod
    def add_evidence(
        case_number: str,
        file_path: str,
        collected_by: str,
        notes: str | None = None,
    ) -> EvidenceItem:
        """Add evidence to a case (hash only). Logs warning if ingestion was unusually slow."""
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")

            # 1. Hash the file (with progress + estimate + slow detection)
            hash_info = calculate_hashes(file_path)

            # 2. Create the evidence record
            evidence = EvidenceItem(
                case_id=case.id,
                original_filename=hash_info["filename"],
                file_size=hash_info["size"],
                mime_type=hash_info["mime_type"],
                sha256_hash=hash_info["sha256"],
                md5_hash=hash_info["md5"],
                collected_by=collected_by,
                notes=notes,
            )
            db.add(evidence)
            db.flush()   # get the ID

            # 3. Prepare custody details (include warning if it occurred)
            custody_details = {
                "filename": hash_info["filename"],
                "sha256": hash_info["sha256"],
                "size": hash_info["size"],
            }

            if hash_info.get("warning"):
                custody_details["warning"] = hash_info["warning"]
                custody_details["note"] = "Ingestion was significantly slower than estimated"

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
