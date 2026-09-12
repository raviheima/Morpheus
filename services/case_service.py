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

# case service export_case_to_json


    @staticmethod
    def export_case_to_json(case_number: str) -> dict:
        """
        Export a full case (metadata + evidence + chain of custody) as a dictionary.
        Ready to be written to a JSON file.
        """
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")

            # Evidence items
            evidence_items = (
                db.query(EvidenceItem)
                .filter(EvidenceItem.case_id == case.id)
                .order_by(EvidenceItem.collected_at.asc())
                .all()
            )

            # Chain of custody
            custody_logs = (
                db.query(ChainOfCustody)
                .filter(ChainOfCustody.case_id == case.id)
                .order_by(ChainOfCustody.timestamp.asc())
                .all()
            )

            export_data = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "case": {
                    "case_number": case.case_number,
                    "case_name": case.case_name,
                    "examiner_name": case.examiner_name,
                    "examiner_email": case.examiner_email,
                    "examiner_notes": case.examiner_notes,
                    "organisation": case.organisation,
                    "description": case.description,
                    "status": case.status,
                    "created_at": case.created_at.isoformat(),
                },
                "evidence": [
                    {
                        "id": item.id,
                        "original_filename": item.original_filename,
                        "file_size": item.file_size,
                        "mime_type": item.mime_type,
                        "sha256_hash": item.sha256_hash,
                        "md5_hash": item.md5_hash,
                        "collected_by": item.collected_by,
                        "collected_at": item.collected_at.isoformat(),
                        "notes": item.notes,
                    }
                    for item in evidence_items
                ],
                "chain_of_custody": [
                    {
                        "id": log.id,
                        "action": log.action,
                        "actor": log.actor,
                        "timestamp": log.timestamp.isoformat(),
                        "details": log.details,
                        "evidence_id": (
                                    # Look up the MD5 if this log is linked to an evidence item
                                    next(
                                        (e.md5_hash for e in evidence_items if e.id == log.evidence_id),
                                        None
                                    )
                                ),
                    }
                    for log in custody_logs
                ],
            }

            return export_data
        finally:
            db.close()
    ## generate markdown report
    @staticmethod
    def generate_markdown_report(case_number: str) -> str:
        """Generate a clean Markdown report for a case."""
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")

            evidence_items = (
                db.query(EvidenceItem)
                .filter(EvidenceItem.case_id == case.id)
                .order_by(EvidenceItem.collected_at.asc())
                .all()
            )

            custody_logs = (
                db.query(ChainOfCustody)
                .filter(ChainOfCustody.case_id == case.id)
                .order_by(ChainOfCustody.timestamp.asc())
                .all()
            )

            lines = []
            lines.append(f"# Forensic Case Report")
            lines.append("")
            lines.append(f"**Case Number:** {case.case_number}")
            lines.append(f"**Case Name:** {case.case_name}")
            lines.append(f"**Organisation:** {case.organisation or '—'}")
            lines.append(f"**Status:** {case.status}")
            lines.append(f"**Created:** {case.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            lines.append("")
            lines.append("## Examiner")
            lines.append(f"- **Name:** {case.examiner_name}")
            lines.append(f"- **Email:** {case.examiner_email or '—'}")
            if case.examiner_notes:
                lines.append(f"- **Notes:** {case.examiner_notes}")
            lines.append("")
            if case.description:
                lines.append("## Description")
                lines.append(case.description)
                lines.append("")

            lines.append("## Evidence Items")
            lines.append("")
            if not evidence_items:
                lines.append("_No evidence items recorded._")
            else:
                for idx, item in enumerate(evidence_items, 1):
                    lines.append(f"### {idx}. {item.original_filename}")
                    lines.append(f"- **Evidence ID (MD5):** `{item.md5_hash}`")
                    lines.append(f"- **SHA-256:** `{item.sha256_hash}`")
                    lines.append(f"- **Size:** {item.file_size:,} bytes")
                    lines.append(f"- **MIME Type:** {item.mime_type or '—'}")
                    lines.append(f"- **Collected by:** {item.collected_by}")
                    lines.append(f"- **Collected at:** {item.collected_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    if item.notes:
                        lines.append(f"- **Notes:** {item.notes}")
                    lines.append("")

            lines.append("## Chain of Custody")
            lines.append("")
            if not custody_logs:
                lines.append("_No custody records._")
            else:
                lines.append("| Timestamp (UTC) | Action | Actor | Details |")
                lines.append("|-----------------|--------|-------|---------|")
                for log in custody_logs:
                    details = log.details or "—"
                    # Make details shorter for the table
                    if len(details) > 60:
                        details = details[:57] + "..."
                    lines.append(
                        f"| {log.timestamp.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"| {log.action} "
                        f"| {log.actor} "
                        f"| {details} |"
                    )

            lines.append("")
            lines.append("---")
            lines.append(f"*Report generated by Morpheus on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*")

            return "\n".join(lines)
        finally:
            db.close()
