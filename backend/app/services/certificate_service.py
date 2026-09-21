from __future__ import annotations

import json
import re
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
        """Normalize core-font text and break oversized unspaced PDF tokens."""
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
        s = s.encode("latin-1", errors="replace").decode("latin-1")
        return re.sub(
            r"\S{21,}",
            lambda match: "\n".join(
                match.group(0)[i : i + 20] for i in range(0, len(match.group(0)), 20)
            ),
            s,
        )

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
            "analysis_started": "Disk analysis started",
            "analysis_completed": "Disk analysis completed",
            "report_downloaded": "Case report downloaded",
            "analysis_started": "Disk analysis started",
            "analysis_completed": "Disk analysis completed",
            "analysis_failed": "Disk analysis failed",
            "case_closed": "Case closed",
            "case_reopened": "Case reopened",
            "case_deleted": "Case marked deleted (log kept)",
            "ai_summary_generated": "AI case summary created",
            "evidence_added": "Evidence artifact registered",
        }
        title = action_map.get(
            log.action, (log.action or "action").replace("_", " ").title()
        )
        detail = ""
        if log.details:
            try:
                d = json.loads(log.details)
                if isinstance(d, dict):
                    parts = []
                    if d.get("filename"):
                        parts.append(f"File: {d['filename']}")
                    if d.get("old_path") and d.get("new_path"):
                        parts.append(f"Path: {d['old_path']} -> {d['new_path']}")
                    elif d.get("path"):
                        parts.append(f"Path: {d['path']}")
                    if d.get("sha256"):
                        parts.append(f"SHA-256: {str(d['sha256'])[:16]}...")
                    if d.get("note"):
                        parts.append(str(d["note"]))
                    if d.get("warning"):
                        parts.append(str(d["warning"]))
                    if d.get("warnings") is not None:
                        parts.append(
                            f"Checked {d.get('total', '?')} file(s); "
                            f"{d.get('ok', 0)} unchanged, "
                            f"{d.get('warnings', 0)} problem(s)."
                        )
                    detail = " | ".join(parts) if parts else ""
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
                .filter(
                    ~(
                        (ChainOfCustody.action == "integrity_check")
                        & (ChainOfCustody.actor == "certificate")
                    )
                )
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


    @staticmethod
    def _latest_presentation(case_number: str) -> Optional[Dict[str, Any]]:
        """Load latest completed analysis presentation for the case, if any."""
        try:
            from app.database import SessionLocal as _SL
            from app.services.analysis_store import latest_for_case, run_to_job_dict

            db = _SL()
            try:
                run = latest_for_case(db, case_number)
                if not run or run.status != "completed":
                    return None
                job = run_to_job_dict(run)
                return job.get("result")
            finally:
                db.close()
        except Exception:
            return None

    @staticmethod
    def write_full_report_pdf(case_number: str, output_path: str | Path) -> Path:
        """
        Case report PDF: case header, integrity snapshot, key analysis findings,
        and full chain of custody. Replaces the old 'certificate' download.
        """
        data = CertificateService.build_certificate_data(case_number)
        presentation = CertificateService._latest_presentation(case_number)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        safe = CertificateService._pdf_safe

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # Title
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, safe("Morpheus Case Report"), ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.ln(2)
        pdf.multi_cell(
            0,
            6,
            safe(
                "This report summarizes integrity status, key findings from disk "
                "analysis (when available), and the chain of custody for the case."
            ),
        )
        pdf.ln(4)

        # Case details
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe("1. Case details"), ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, safe(f"Case number: {data['case_number']}"), ln=True)
        pdf.cell(0, 6, safe(f"Case name: {data['case_name']}"), ln=True)
        pdf.cell(0, 6, safe(f"Examiner: {data['examiner_name']}"), ln=True)
        if data.get("organisation"):
            pdf.cell(0, 6, safe(f"Organisation: {data['organisation']}"), ln=True)
        pdf.cell(
            0,
            6,
            safe(f"Generated: {CertificateService._fmt_dt(data['generated_at'])}"),
            ln=True,
        )
        pdf.ln(3)

        # Integrity
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe(f"2. Integrity: {data['overall_status']}"), ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, safe(data["overall_summary"]))
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        for ds in data["data_sources"]:
            status = "OK" if ds["consistent"] else "PROBLEM"
            block = (
                f"- {ds['label']} ({ds['filename']})\n"
                f"  Path: {ds.get('path') or 'n/a'}\n"
                f"  SHA-256: {ds['fingerprint']}\n"
                f"  Status: {status}"
            )
            if ds.get("warning"):
                block += f"\n  Note: {ds['warning']}"
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, safe(block))
            pdf.ln(1)

        # Analysis findings
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe("3. Key analysis findings"), ln=True)
        pdf.set_font("Helvetica", "", 10)

        if not presentation:
            pdf.multi_cell(
                0,
                5,
                safe(
                    "No completed disk analysis is stored for this case yet. "
                    "Run Analyze on a data source, then download this report again."
                ),
            )
        else:
            cs = presentation.get("case_summary") or {}
            lines = [
                f"Files scanned: {cs.get('total_files_scanned', '—')}",
                f"Deleted recovered: {cs.get('total_deleted_recovered', cs.get('total_deleted_found', '—'))}",
                f"Emails: {cs.get('total_emails_parsed', '—')}",
                f"Browser history entries: {cs.get('total_browser_history_entries', '—')}",
                f"Volumes: {cs.get('total_volumes_scanned', '—')}",
            ]
            for line in lines:
                pdf.cell(0, 5, safe(f"- {line}"), ln=True)

            # Documents of interest (capped)
            docs = presentation.get("documents_of_interest") or presentation.get(
                "documents"
            ) or []
            if isinstance(docs, list) and docs:
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 6, safe("Documents of interest (sample)"), ln=True)
                pdf.set_font("Helvetica", "", 9)
                for doc in docs[:12]:
                    if isinstance(doc, dict):
                        name = doc.get("name") or doc.get("path") or str(doc)
                        p = doc.get("path") or ""
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(0, 4, safe(f"- {name}" + (f"  [{p}]" if p else "")))
                    else:
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(0, 4, safe(f"- {doc}"))

            emails = presentation.get("emails") or []
            if isinstance(emails, list) and emails:
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 6, safe("Email artifacts (sample)"), ln=True)
                pdf.set_font("Helvetica", "", 9)
                for em in emails[:8]:
                    if not isinstance(em, dict):
                        continue
                    subj = em.get("subject") or "(no subject)"
                    frm = em.get("from") or em.get("sender") or "?"
                    pdf.set_x(pdf.l_margin)
                    pdf.multi_cell(0, 4, safe(f"- {subj}  (from {frm})"))

            suspicious = presentation.get("suspicious") or presentation.get(
                "suspicious_items"
            ) or []
            if isinstance(suspicious, list) and suspicious:
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 6, safe("Suspicious / notable items (sample)"), ln=True)
                pdf.set_font("Helvetica", "", 9)
                for s in suspicious[:10]:
                    if isinstance(s, dict):
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(
                            0,
                            4,
                            safe(f"- {s.get('name') or s.get('path') or s}"),
                        )
                    else:
                        pdf.set_x(pdf.l_margin)
                        pdf.multi_cell(0, 4, safe(f"- {s}"))

        # Custody
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, safe("4. Chain of custody"), ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(
            0,
            5,
            safe(
                "Chronological record of who handled case records and what actions "
                "were taken."
            ),
        )
        pdf.ln(2)
        if not data["custody_timeline"]:
            pdf.cell(0, 6, safe("No custody entries yet."), ln=True)
        for entry in data["custody_timeline"]:
            block = f"{entry['when']} - {entry['who']}\n  {entry['what']}"
            if entry.get("detail"):
                block += f"\n  {entry['detail']}"
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, safe(block))
            pdf.ln(1)

        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(
            0,
            5,
            safe(
                "A fingerprint (SHA-256) is computed from file contents. Matching "
                "fingerprints mean content is unchanged since registration. The path "
                "only indicates where the system reads the file."
            ),
        )

        pdf.output(str(output_path))
        return output_path
