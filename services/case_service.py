from datetime import datetime, timezone
import uuid
import json
from typing import Optional, List
from database import SessionLocal, Case, ChainOfCustody, EvidenceItem


class CaseService:
    """Handles all case-related operations."""

    @staticmethod
    def create_case(
        case_name: str,
        examiner_name: str,
        examiner_email: Optional[str] = None,
        examiner_notes: Optional[str] = None,
        organisation: Optional[str] = None,
        description: Optional[str] = None,
        case_number: Optional[str] = None,
    ) -> Case:
        if not case_number:
            date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
            short_id = str(uuid.uuid4())[:4].upper()
            case_number = f"CASE-{date_part}-{short_id}"

        db = SessionLocal()
        try:
            new_case = Case(
                case_number=case_number,
                case_name=case_name,
                examiner_name=examiner_name,
                examiner_email=examiner_email,
                examiner_notes=examiner_notes,
                organisation=organisation,
                description=description,
            )
            db.add(new_case)
            db.flush()

            # Chain of Custody
            custody = ChainOfCustody(
                case_id=new_case.id,
                action="case_created",
                actor=examiner_name,
                details=json.dumps({
                    "case_name": case_name,
                    "organisation": organisation,
                    "examiner_email": examiner_email,
                }),
            )
            db.add(custody)
            db.commit()
            db.refresh(new_case)
            return new_case
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def list_cases() -> List[Case]:
        db = SessionLocal()
        try:
            return db.query(Case).order_by(Case.created_at.desc()).all()
        finally:
            db.close()

    @staticmethod
    def get_case_by_number(case_number: str) -> Optional[Case]:
        db = SessionLocal()
        try:
            return db.query(Case).filter(Case.case_number == case_number).first()
        finally:
            db.close()

    @staticmethod
    def get_case_details(case_number: str):
        """Return full case info + evidence count"""
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                return None

            evidence_count = (
                db.query(EvidenceItem)
                .filter(EvidenceItem.case_id == case.id)
                .count()
            )
            return case, evidence_count
        finally:
            db.close()


    @staticmethod
    def get_custody_timeline(case_number: str):
        """Return the full chain of custody for a case"""
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                return None

            logs = (
                db.query(ChainOfCustody)
                .filter(ChainOfCustody.case_id == case.id)
                .order_by(ChainOfCustody.timestamp.asc())
                .all()
            )
            return case, logs
        finally:
            db.close()
