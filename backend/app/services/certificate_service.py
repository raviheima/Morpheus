from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fpdf import FPDF

from app.database import SessionLocal, Case, DataSource, EvidenceItem, ChainOfCustody
from app.services.integrity_service import IntegrityService


class CertificateService:
    """
    Court-facing integrity certificate and plain-language custody report.
    Hash is the content identity; path is only where we re-read the file.
    """

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pdf_safe(text: Any) -> str:
        """Helvetica core fonts only support a latin-1-ish range."""
        if text is None:
            return ""
        s = str(text)
        replacements = {
            "\u2014": "-",  # em dash
            "\u2013": "-",  # en dash
            "\u2018": "'",
            "\u2019": "'",
            "\u201c": '"',
            "\u201d": '"',
            "\u2026": "...",
            "\u00a0": " ",
        }
        for a, b in replacements.items():
            s = s.replace(a, b)
        return s.encode("latin-1", errors="replace").decode("latin-1")

    @staticmethod
    def _fmt_dt(dt: Optional[datetime]) -> str:
        if not dt:
            return "unknown"
        if dt.tzinfo is None:
            return dt.strftime("%d %B %Y, %H:%M UTC")
        return dt.astimezone(timezone.utc).strftime("%d %B %Y, %H:%M UTC")

    @staticmethod
    def _plain_custody(log: ChainOfCustody) -> Dict[str, str]:
        action_map = {
            "case_created": "Case opened",
            "data_source_added": "Main evidence file registered",
            "evidence_added": "Additional file registered",
            "integrity_check": "Integrity check performed",
            "data_source_warning": "Warning: file may have changed or gone missing",
            "evidence_warning": "Warning: file may have changed or gone missing",
            "path_updated": "File location updated (same fingerprint confirmed)",
        }
        title = action_map.get(
            log.action, (log.action or "action").replace("_", " ").title()
        )
        detail = ""
        if log.details:
            try:
                d = json.loads(log.details)
                if isinstance(d, dict):
                    if d.get("filename"):
                        detail = f"File: {d['filename']}"
                    elif d.get("warning"):
                        detail = str(d["warning"])
                    elif d.get("warnings") is not None:
                        detail = (
                            f"Checked {d.get('total', '?')} file(s); "
                            f"{d.get('ok', 0)} unchanged, "
                            f"{d.get('warnings', 0)} problem(s)."
                        )
            except Exception:
                detail = ""

        return {
            "when": CertificateService._fmt_dt(log.timestamp),
            "who": log.actor or "system",
            "what": title,
            "detail": detail,
        }

    # ------------------------------------------------------------------ #
    # Data
    # ------------------------------------------------------------------ #

    @staticmethod
    def build_certificate_data(case_number: str) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")

            integrity = IntegrityService.check_case(case_number, actor="certificate")

            data_sources = (
                db.query(DataSource)
                .filter(DataSource.case_id == case.id)
                .order_by(DataSource.collected_at.asc())
                .all()
            )
            evidence = (
                db.query(EvidenceItem)
                .filter(EvidenceItem.case_id == case.id)
                .order_by(EvidenceItem.collected_at.asc())
                .all()
            )
            logs = (
                db.query(ChainOfCustody)
                .filter(ChainOfCustody.case_id == case.id)
                .order_by(ChainOfCustody.timestamp.asc())
                .all()
            )

            all_ok = integrity.warnings == 0

            return {
                "case_number": case.case_number,
                "case_name": case.case_name,
                "examiner_name": case.examiner_name,
                "organisation": case.organisation,
                "generated_at": datetime.now(timezone.utc),
                "overall_status": "UNCHANGED" if all_ok else "PROBLEM DETECTED",
                "overall_summary": (
                    "All recorded files match the fingerprints taken when they "
                    "were first registered."
                    if all_ok
                    else "One or more files are missing or no longer match the "
                    "fingerprint recorded at collection. See details below."
                ),
                "integrity": integrity.model_dump()
                if hasattr(integrity, "model_dump")
                else dict(integrity),
                "data_sources": [
                    {
                        "label": ds.label or ds.original_filename,
                        "filename": ds.original_filename,
                        "path": ds.stored_path,
                        "collected_by": ds.collected_by,
                        "collected_at": ds.collected_at,
                        "fingerprint": ds.sha256_hash,
                        "consistent": bool(ds.is_consistent),
                        "warning": ds.last_warning,
                    }
                    for ds in data_sources
                ],
                "evidence": [
                    {
                        "filename": ev.original_filename,
                        "path": getattr(ev, "stored_path", None),
                        "collected_by": ev.collected_by,
                        "collected_at": ev.collected_at,
                        "fingerprint": ev.sha256_hash,
                        "consistent": bool(getattr(ev, "is_consistent", True)),
                        "warning": getattr(ev, "last_warning", None),
                    }
                    for ev in evidence
                ],
                "custody_timeline": [
                    CertificateService._plain_custody(log) for log in logs
                ],
            }
        finally:
            db.close()

    # ------------------------------------------------------------------ #
    # PDF
    # ------------------------------------------------------------------ #

    @staticmethod
    def write_pdf(case_number: str, output_path: str | Path) -> Path:
        data = CertificateService.build_certificate_data(case_number)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        safe = CertificateService._pdf_safe

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, safe("Evidence Integrity Certificate"), ln=True)

        pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)
        pdf.multi_cell(
            0,
            6,
            safe(
                "This document records digital evidence for a case and whether "
                "those files still match the fingerprints taken when they were "
                "first registered. It is intended for investigators, panels, "
                "and the court."
            ),
        )
        pdf.ln(4)

        # Case details
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe("Case details"), ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, safe(f"Case number: {data['case_number']}"), ln=True)
        pdf.cell(0, 6, safe(f"Case name: {data['case_name']}"), ln=True)
        pdf.cell(0, 6, safe(f"Recorded by: {data['examiner_name']}"), ln=True)
        if data.get("organisation"):
            pdf.cell(0, 6, safe(f"Organisation: {data['organisation']}"), ln=True)
        pdf.cell(
            0,
            6,
            safe(
                f"Certificate generated: "
                f"{CertificateService._fmt_dt(data['generated_at'])}"
            ),
            ln=True,
        )
        pdf.ln(4)

        # Overall result
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe(f"Overall result: {data['overall_status']}"), ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, safe(data["overall_summary"]))
        pdf.ln(4)

        # Data sources
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe("Registered main evidence (data sources)"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        if not data["data_sources"]:
            pdf.cell(0, 6, safe("None registered."), ln=True)
        for ds in data["data_sources"]:
            status = "Unchanged" if ds["consistent"] else "PROBLEM"
            collected = CertificateService._fmt_dt(ds.get("collected_at"))
            block = (
                f"- {ds['label']} ({ds['filename']})\n"
                f"  Collected by {ds['collected_by']} on {collected}\n"
                f"  Fingerprint (SHA-256): {ds['fingerprint']}\n"
                f"  Status: {status}"
            )
            if ds.get("warning"):
                block += f"\n  Note: {ds['warning']}"
            pdf.multi_cell(0, 5, safe(block))
            pdf.ln(2)

        # Other evidence
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe("Other registered files"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        if not data["evidence"]:
            pdf.cell(0, 6, safe("None registered."), ln=True)
        for ev in data["evidence"]:
            status = "Unchanged" if ev["consistent"] else "PROBLEM"
            block = (
                f"- {ev['filename']}\n"
                f"  Collected by {ev['collected_by']}\n"
                f"  Fingerprint (SHA-256): {ev['fingerprint']}\n"
                f"  Status: {status}"
            )
            if ev.get("warning"):
                block += f"\n  Note: {ev['warning']}"
            pdf.multi_cell(0, 5, safe(block))
            pdf.ln(1)

        # Custody page
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe("Chain of handling (custody)"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(
            0,
            5,
            safe(
                "This list shows who handled the case records and what they did, "
                "in order from first to last."
            ),
        )
        pdf.ln(2)

        if not data["custody_timeline"]:
            pdf.cell(0, 6, safe("No custody entries yet."), ln=True)
        for entry in data["custody_timeline"]:
            block = (
                f"{entry['when']} - {entry['who']}\n"
                f"  {entry['what']}"
            )
            if entry.get("detail"):
                block += f"\n  {entry['detail']}"
            pdf.multi_cell(0, 5, safe(block))
            pdf.ln(2)

        # Footer note
        pdf.ln(6)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(
            0,
            5,
            safe(
                "A fingerprint is a unique value computed from the file contents. "
                "If even one character in the file changes, the fingerprint changes. "
                "Matching fingerprints mean the file content is the same as when it "
                "was registered. The file path only tells the system where to read "
                "the file; the fingerprint is the identity of the content."
            ),
        )

        pdf.output(str(output_path))
        return output_path

    # ------------------------------------------------------------------ #
    # Markdown
    # ------------------------------------------------------------------ #

    @staticmethod
    def write_markdown(case_number: str, output_path: str | Path) -> Path:
        data = CertificateService.build_certificate_data(case_number)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Evidence Integrity Certificate",
            "",
            data["overall_summary"],
            "",
            f"**Overall result:** {data['overall_status']}",
            "",
            "## Case details",
            f"- Case number: {data['case_number']}",
            f"- Case name: {data['case_name']}",
            f"- Recorded by: {data['examiner_name']}",
            f"- Generated: {CertificateService._fmt_dt(data['generated_at'])}",
            "",
            "## Main evidence files",
        ]
        for ds in data["data_sources"]:
            status = "Unchanged" if ds["consistent"] else "PROBLEM"
            lines.append(
                f"- **{ds['label']}** - fingerprint `{ds['fingerprint']}` - {status}"
            )
        lines += ["", "## Other files", ""]
        if not data["evidence"]:
            lines.append("None registered.")
        for ev in data["evidence"]:
            status = "Unchanged" if ev["consistent"] else "PROBLEM"
            lines.append(
                f"- **{ev['filename']}** - fingerprint `{ev['fingerprint']}` - {status}"
            )
        lines += ["", "## Custody timeline", ""]
        for e in data["custody_timeline"]:
            lines.append(f"- **{e['when']}** - {e['who']}: {e['what']}")
            if e.get("detail"):
                lines.append(f"  - {e['detail']}")
        lines += [
            "",
            "---",
            "",
            "A fingerprint is computed from file contents. Matching fingerprints "
            "mean the content is unchanged since registration.",
        ]

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path
