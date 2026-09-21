import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fpdf import FPDF

from app.analysis.report_rules import browser_rules, document_rules


def _report_items(items: list, report_mode: str, summary_limit: int) -> list:
    """Return all items in full mode, or a bounded summary selection."""
    if report_mode == "full":
        return items
    return items[:summary_limit]


def _append_scope_notice(lines: list, label: str, total: int, report_mode: str, summary_limit: int) -> None:
    if report_mode == "full" or total <= summary_limit:
        return
    lines.append(f"Showing {summary_limit} of {total} {label}. Use full report mode for all items.")


def format_report(
    report: Dict[str, Any],
    include_appendix: bool = False,
    report_mode: str = "summary",
) -> str:
    """
    Formats the analysis report dictionary into a clean, investigator-friendly,
    structured text/markdown report.

    ``summary`` is concise and explicitly labels limited sections.
    ``full`` includes every available item in the report.
    """
    if report_mode not in {"summary", "full"}:
        raise ValueError("report_mode must be 'summary' or 'full'")

    lines = []

    # 1. Header
    target = report.get("target", "Unknown Target")
    ident = report.get("identification") or {}
    summary = report.get("summary") or {}
    engine = report.get("engine") or {}
    now_str = report.get("analysis_completed_at") or report.get("analysis_started_at") or datetime.now(timezone.utc).isoformat()
    status = report.get("status", "unknown")

    lines.append("=" * 65)
    lines.append("MORPHEUS FORENSIC ANALYSIS REPORT")
    lines.append("=" * 65)
    lines.append(f"Report ID             : {report.get('report_id', 'Not assigned')}")
    lines.append(f"Evidence Target       : {target}")
    lines.append(f"Image Type            : {ident.get('image_type', 'Unknown')}")
    lines.append(f"Partition Scheme      : {ident.get('partition_scheme', 'Unknown')}")
    lines.append(f"Operating System      : {'Detected' if ident.get('is_operating_system') else 'Not detected'}")
    lines.append(f"Analysis Completed    : {now_str}")
    lines.append(f"Analysis Status       : {status}")
    lines.append(f"Analysis Duration     : {report.get('analysis_duration_seconds', 'Unknown')} seconds")
    lines.append(f"Report Mode           : {report_mode}")
    lines.append(f"Tool Version          : {engine.get('name', 'Morpheus Analysis Engine')} v{engine.get('version', 'Unknown')}")
    lines.append("")

    # 2. Executive Summary
    lines.append("-" * 65)
    lines.append("EXECUTIVE SUMMARY (KEY FINDINGS)")
    lines.append("-" * 65)
    if report.get("errors"):
        lines.append(f"• Processing warnings/errors : {len(report['errors'])} (see Limitations)")

    scanned_vols = summary.get("total_volumes_scanned", 0)
    found_vols = summary.get("total_volumes_found", 0)
    nested_vhds = summary.get("nested_vhds", 0)
    total_files = summary.get("total_files_scanned", 0)
    deleted_files = summary.get("total_deleted_found", 0)
    email_cnt = summary.get("total_emails_parsed", 0)
    history_cnt = summary.get("total_browser_history_entries", 0)

    lines.append(f"• Volumes Scanned : {scanned_vols} of {found_vols} partitions ({nested_vhds} nested VHDs found)")
    lines.append(f"• Files Analyzed  : {total_files:,} total files ({deleted_files} deleted files identified)")
    lines.append(f"• Communications  : {email_cnt} emails parsed ({summary.get('total_email_attachments', 0)} attachments)")
    lines.append(f"• Web History     : {history_cnt} browser history entries recovered")
    lines.append("")

    # Collect Documents of Interest
    docs_encrypted = []
    docs_recycle_plain = []
    docs_user = []
    notable_emails = []
    notable_browser = []
    encryption_artifacts = []

    for vol in report.get("volume_scans", []):
        scan = vol.get("scan_result") or {}

        # Encryption software artifacts
        for enc in scan.get("encryption_related", []):
            encryption_artifacts.append(f"[{vol.get('description', 'Volume')}] {enc.get('path')}")

        # Emails
        email_analysis = vol.get("email_analysis") or {}
        for eml in email_analysis.get("parsed_emails", []):
            notable_emails.append(eml)

        # Browser
        browser_analysis = vol.get("browser_analysis") or {}
        for ie in browser_analysis.get("internet_explorer", []):
            for entry in ie.get("entries", []):
                url = entry.get("url", "")
                matched_rules = browser_rules(url)
                if matched_rules:
                    item = dict(entry)
                    item["detection_rules"] = matched_rules
                    notable_browser.append(item)

        # Documents & Text files
        for doc in scan.get("documents", []):
            p = doc.get("path", "")
            lower_p = p.lower()
            if lower_p.endswith(".txt"):
                matched_rules = document_rules(p)
                rule_ids = {rule["id"] for rule in matched_rules}
                if "document_bctextencoder" in rule_ids:
                    docs_encrypted.append({**doc, "detection_rules": matched_rules})
                elif "document_recycle_bin" in rule_ids:
                    docs_recycle_plain.append({**doc, "detection_rules": matched_rules})
                elif "document_user_path" in rule_ids:
                    docs_user.append({**doc, "detection_rules": matched_rules})

    # 3. Documents of Interest
    lines.append("-" * 65)
    lines.append("DOCUMENTS OF INTEREST")
    lines.append("-" * 65)

    if docs_encrypted:
        lines.append("\n[ENCRYPTED COMMUNICATIONS]")
        _append_scope_notice(lines, "encrypted documents", len(docs_encrypted), report_mode, 5)
        for doc in _report_items(docs_encrypted, report_mode, 5):
            lines.append(f"  • Path   : {doc.get('path')}")
            lines.append(f"    Format : BCTextEncoder / Encrypted Text")
            lines.append(f"    Status : Encrypted (Ciphertext Header Detected)")
            lines.append(f"    Rules  : {', '.join(rule['name'] for rule in doc.get('detection_rules', []))}")
            lines.append(f"    Size   : {doc.get('size', 0):,} bytes")
            lines.append("")

    if docs_recycle_plain:
        lines.append("[RECYCLE BIN — RECOVERED PLAIN TEXT]")
        _append_scope_notice(lines, "recovered plain-text documents", len(docs_recycle_plain), report_mode, 5)
        for doc in _report_items(docs_recycle_plain, report_mode, 5):
            lines.append(f"  • Path   : {doc.get('path')}")
            lines.append(f"    Status : Deleted (Recovered from $RECYCLE.BIN)")
            lines.append(f"    Rules  : {', '.join(rule['name'] for rule in doc.get('detection_rules', []))}")
            lines.append(f"    Size   : {doc.get('size', 0):,} bytes")
            lines.append("")

    if docs_user:
        lines.append("[USER DOCUMENTS]")
        _append_scope_notice(lines, "user documents", len(docs_user), report_mode, 6)
        for doc in _report_items(docs_user, report_mode, 6):
            lines.append(f"  • Path   : {doc.get('path')}")
            lines.append(f"    Size   : {doc.get('size', 0):,} bytes")
            lines.append("")

    # 4. Email Summary
    lines.append("-" * 65)
    lines.append("EMAIL ARTIFACTS")
    lines.append("-" * 65)
    lines.append(f"Parsed Emails: {summary.get('total_emails_parsed', 0)} | Attachments: {summary.get('total_email_attachments', 0)}")
    lines.append("")

    if notable_emails:
        lines.append("Sample Emails:")
        _append_scope_notice(lines, "emails", len(notable_emails), report_mode, 6)
        for eml in _report_items(notable_emails, report_mode, 6):
            date_str = eml.get("date", "Unknown Date")
            sender = eml.get("from", "Unknown")
            recipient = eml.get("to", "Unknown")
            subj = eml.get("subject", "(No Subject)")
            snippet = eml.get("body_snippet", "")[:100].replace("\n", " ").replace("\r", " ")
            atts = len(eml.get("attachments", []))
            att_str = f" [atts={atts}]" if atts > 0 else ""

            lines.append(f"  [{date_str}]")
            lines.append(f"  From    : {sender}")
            lines.append(f"  To      : {recipient}{att_str}")
            lines.append(f"  Subject : {subj}")
            lines.append(f"  Snippet : {snippet}...")
            lines.append("")

    # 5. Browser History
    lines.append("-" * 65)
    lines.append("BROWSER HISTORY (HIGH SIGNAL RECOVERIES)")
    lines.append("-" * 65)
    lines.append(f"Recovered Entries: {history_cnt} entries")
    lines.append("")

    if notable_browser:
        lines.append("Notable Web Searches & Visited Sites:")
        seen_urls = set()
        _append_scope_notice(lines, "browser history entries", len(notable_browser), report_mode, 12)
        for item in _report_items(notable_browser, report_mode, 12):
            url = item.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            ts = item.get("last_accessed") or item.get("last_modified") or "no-timestamp"
            hits = item.get("access_count", 1)
            display_url = url if len(url) <= 90 else url[:87] + "..."
            rule_names = ', '.join(rule['name'] for rule in item.get('detection_rules', []))
            lines.append(f"  [{ts}]  hits={hits:<3}  {display_url}")
            lines.append(f"      Rules: {rule_names}")
        lines.append("")

    # 6. Nested Virtual Disks & Encryption
    lines.append("-" * 65)
    lines.append("NESTED VIRTUAL DISKS & ENCRYPTION ARTIFACTS")
    lines.append("-" * 65)

    vhds = report.get("nested_virtual_disks", [])
    if not vhds:
        lines.append("No nested virtual disks found.")
    else:
        for idx, vhd in enumerate(vhds, 1):
            v_path = vhd.get("vhd_path", "Unknown VHD")
            ident_vhd = vhd.get("identification", {})
            lines.append(f"Nested VHD #{idx}: {v_path}")
            lines.append(f"  Type             : {ident_vhd.get('image_type', 'VHD')}")
            lines.append(f"  Partition Scheme : {ident_vhd.get('partition_scheme', 'GPT')}")
            lines.append(f"  Volumes Found    : {len(ident_vhd.get('volumes', []))}")
            lines.append("")

    if encryption_artifacts:
        lines.append("Encryption Binaries / Configs Detected:")
        for enc_item in encryption_artifacts[:6]:
            lines.append(f"  • {enc_item}")
        lines.append("")

    # 7. Processing Limitations
    lines.append("-" * 65)
    lines.append("PROCESSING LIMITATIONS AND ERRORS")
    lines.append("-" * 65)
    errors = report.get("errors") or []
    if errors:
        for error in errors:
            lines.append(f"• {error}")
    else:
        lines.append("No processing errors were recorded.")
    lines.append("")

    # 8. Volume Inventory
    lines.append("-" * 65)
    lines.append("VOLUME INVENTORY & SUMMARY COUNTS")
    lines.append("-" * 65)
    lines.append(f"Total Files Scanned      : {summary.get('total_files_scanned', 0):,}")
    lines.append(f"Deleted Files Recovered  : {summary.get('total_deleted_found', 0):,}")
    lines.append(f"Emails Identified        : {summary.get('total_emails', 0):,}")
    lines.append(f"Documents Identified     : {summary.get('total_documents', 0):,}")
    lines.append(f"Images Identified        : {summary.get('total_images', 0):,}")
    lines.append(f"Registry Hives           : {summary.get('total_registry_hives', 0):,}")
    lines.append(f"Event Logs (.evtx)       : {summary.get('total_event_logs', 0):,}")
    lines.append(f"Browser Artifacts        : {summary.get('total_browser_artifacts', 0):,}")
    lines.append("=" * 65)

    return "\n".join(lines)


def export_report_json(
    report: Dict[str, Any],
    output_path: str,
    presentation_only: bool = False,
    report_mode: str = "summary",
):
    """
    Exports the report to a JSON file.
    If presentation_only is True, exports a curated subset ideal for demos & pitch decks.
    """
    if report_mode not in {"summary", "full"}:
        raise ValueError("report_mode must be 'summary' or 'full'")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not presentation_only:
        export_data = dict(report)
        export_data["report_mode"] = report_mode
        export_data["export_scope"] = "complete analysis report"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, default=str)
        return
    # Slim presentation JSON
    summary = report.get("summary", {})
    ident = report.get("identification", {})

    presentation_data = {
        "report_mode": report_mode,
        "export_scope": "presentation summary",
        "case_summary": {
            "report_id": report.get("report_id"),
            "status": report.get("status"),
            "analysis_started_at": report.get("analysis_started_at"),
            "analysis_completed_at": report.get("analysis_completed_at"),
            "analysis_duration_seconds": report.get("analysis_duration_seconds"),
            "engine": report.get("engine"),
            "processing_errors": len(report.get("errors") or []),
            "target": report.get("target"),
            "image_type": ident.get("image_type"),
            "is_operating_system": ident.get("is_operating_system"),
            "total_files_scanned": summary.get("total_files_scanned"),
            "total_deleted_recovered": summary.get("total_deleted_found"),
            "total_emails_parsed": summary.get("total_emails_parsed"),
            "total_browser_history_entries": summary.get("total_browser_history_entries"),
        },
        "documents_of_interest": [],
        "sample_emails": [],
        "sample_web_history": [],
        "nested_virtual_disks": report.get("nested_virtual_disks", []),
    }

    # Extract presentation highlights
    for vol in report.get("volume_scans", []):
        scan = vol.get("scan_result") or {}
        for doc in scan.get("documents", []):
            p = doc.get("path", "").lower()
            matched_rules = document_rules(p)
            if matched_rules:
                presentation_data["documents_of_interest"].append({**doc, "detection_rules": matched_rules})

        email_analysis = vol.get("email_analysis") or {}
        for eml in email_analysis.get("parsed_emails", [])[:5]:
            presentation_data["sample_emails"].append(eml)

        browser_analysis = vol.get("browser_analysis") or {}
        for ie in browser_analysis.get("internet_explorer", []):
            for entry in ie.get("entries", []):
                matched_rules = browser_rules(entry.get("url", ""))
                if matched_rules:
                    presentation_data["sample_web_history"].append({**entry, "detection_rules": matched_rules})

    with open(path, "w", encoding="utf-8") as f:
        json.dump(presentation_data, f, indent=2, default=str)


def export_report_markdown(
    report: Dict[str, Any], output_path: str, report_mode: str = "summary"
) -> str:
    """
    Exports the forensic report as a GitHub-Flavored Markdown (.md) file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    text_report = format_report(report, include_appendix=False, report_mode=report_mode)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text_report + "\n")
    return str(path)


def export_report_pdf(
    report: Dict[str, Any], output_path: str, report_mode: str = "summary"
) -> str:
    """
    Generates a professional, investigator-ready PDF report document.
    """
    if report_mode not in {"summary", "full"}:
        raise ValueError("report_mode must be 'summary' or 'full'")

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    class ForensicPDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 9)
            self.set_text_color(100, 110, 125)
            self.cell(0, 8, 'MORPHEUS DIGITAL FORENSIC ANALYSIS REPORT', align='R')
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(140, 140, 140)
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}} - CONFIDENTIAL FORENSIC REPORT', align='C')

    pdf = ForensicPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    HEADER_BG = (24, 43, 73)
    SECTION_BG = (240, 244, 248)
    TEXT_DARK = (30, 30, 30)

    # Title Banner
    pdf.set_fill_color(*HEADER_BG)
    pdf.rect(10, 18, 190, 14, style='F')
    pdf.set_font('Helvetica', 'B', 13)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(14, 20)
    pdf.cell(0, 10, 'MORPHEUS FORENSIC ANALYSIS REPORT')
    pdf.ln(14)

    # Metadata Section
    target = report.get("target", "Unknown Target")
    ident = report.get("identification") or {}
    summary = report.get("summary") or {}
    engine = report.get("engine") or {}
    analysis_timestamp = report.get("analysis_completed_at") or report.get("analysis_started_at") or datetime.now(timezone.utc).isoformat()

    meta_items = [
        ("Report ID", report.get("report_id", "Not assigned")),
        ("Evidence Target", target),
        ("Image Format", ident.get("image_type", "Unknown")),
        ("Partition Scheme", ident.get("partition_scheme", "Unknown")),
        ("Operating System", "Detected" if ident.get("is_operating_system") else "Not detected"),
        ("Analysis Completed", analysis_timestamp),
        ("Analysis Status", report.get("status", "Unknown")),
        ("Analysis Duration", f"{report.get('analysis_duration_seconds', 'Unknown')} seconds"),
        ("Report Mode", report_mode),
        ("Engine Version", f"{engine.get('name', 'Morpheus Analysis Engine')} v{engine.get('version', 'Unknown')}"),
    ]

    for label, val in meta_items:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'B', 9)
        pdf.set_text_color(50, 60, 75)
        pdf.cell(45, 6, f"{label}:")
        pdf.set_font('Helvetica', '', 9)
        pdf.set_text_color(*TEXT_DARK)
        pdf.cell(0, 6, str(val), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)

    def add_section_header(title):
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'B', 10)
        pdf.set_fill_color(220, 230, 242)
        pdf.set_text_color(20, 40, 70)
        pdf.cell(0, 7, f"  {title.upper()}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*TEXT_DARK)
        pdf.ln(2)

    # 1. Executive Summary
    add_section_header("Executive Summary (Key Findings)")
    pdf.set_font('Helvetica', '', 9)

    scanned_vols = summary.get("total_volumes_scanned", 0)
    found_vols = summary.get("total_volumes_found", 0)
    nested_vhds = summary.get("nested_vhds", 0)
    total_files = summary.get("total_files_scanned", 0)
    deleted_files = summary.get("total_deleted_found", 0)
    email_cnt = summary.get("total_emails_parsed", 0)
    history_cnt = summary.get("total_browser_history_entries", 0)

    bullets = [
        f"Volumes Scanned: {scanned_vols} of {found_vols} partitions ({nested_vhds} nested VHDs discovered)",
        f"Files Analyzed: {total_files:,} total files scanned ({deleted_files} deleted files identified)",
        f"Email Artifacts: {email_cnt} emails parsed ({summary.get('total_email_attachments', 0)} attachments recovered)",
        f"Web History: {history_cnt} browser history entries recovered (IE WebCache / ESE)",
    ]
    for b in bullets:
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5, f"- {b}")
    pdf.ln(4)

    # 2. Documents of Interest
    add_section_header("Documents of Interest & Encrypted Files")
    docs_found = False
    for vol in report.get("volume_scans", []):
        scan = vol.get("scan_result") or {}
        for doc in scan.get("documents", []):
            p = doc.get("path", "")
            matched_rules = document_rules(p)
            if matched_rules:
                docs_found = True
                pdf.set_x(pdf.l_margin)
                pdf.set_font('Helvetica', 'B', 8)
                pdf.multi_cell(0, 4, f"Path: {p}")
                pdf.set_font('Helvetica', '', 8)
                size_str = f"Size: {doc.get('size', 0):,} bytes"
                del_str = " | Deleted: True" if doc.get("deleted") else ""
                rule_names = ', '.join(rule['name'] for rule in matched_rules)
                pdf.cell(0, 4, f"Status: {size_str}{del_str}", new_x="LMARGIN", new_y="NEXT")
                pdf.multi_cell(0, 4, f"Rules: {rule_names}")
                pdf.ln(1)

    if not docs_found:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'I', 9)
        pdf.cell(0, 5, "No high-interest encoded/deleted document artifacts detected.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # 3. Email Artifacts
    add_section_header("Email Artifacts")
    emails_list = []
    for vol in report.get("volume_scans", []):
        email_analysis = vol.get("email_analysis") or {}
        emails_list.extend(email_analysis.get("parsed_emails", []))

    if emails_list:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(35, 5, "Date", border=1)
        pdf.cell(50, 5, "From", border=1)
        pdf.cell(50, 5, "To", border=1)
        pdf.cell(55, 5, "Subject", border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 8)
        if report_mode == "summary" and len(emails_list) > 8:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, f"Showing 8 of {len(emails_list)} emails. Use full report mode for all items.")
        for eml in _report_items(emails_list, report_mode, 8):
            d = str(eml.get("date", ""))[:18]
            f_sender = str(eml.get("from", ""))[:25]
            t_recip = str(eml.get("to", ""))[:25]
            s_subj = str(eml.get("subject", ""))[:28]

            pdf.set_x(pdf.l_margin)
            pdf.cell(35, 5, d, border=1)
            pdf.cell(50, 5, f_sender, border=1)
            pdf.cell(50, 5, t_recip, border=1)
            pdf.cell(55, 5, s_subj, border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'I', 9)
        pdf.cell(0, 5, "No email artifacts recovered.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # 4. Web History
    add_section_header("Recovered Web History (High Signal Searches)")
    history_entries = []
    for vol in report.get("volume_scans", []):
        browser_analysis = vol.get("browser_analysis") or {}
        for ie in browser_analysis.get("internet_explorer", []):
            for entry in ie.get("entries", []):
                url = entry.get("url", "")
                matched_rules = browser_rules(url)
                if matched_rules:
                    history_entries.append({**entry, "detection_rules": matched_rules})

    if history_entries:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(35, 5, "Timestamp", border=1)
        pdf.cell(15, 5, "Hits", border=1)
        pdf.cell(140, 5, "URL / Search Query", border=1, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font('Helvetica', '', 8)
        seen_urls = set()
        if report_mode == "summary" and len(history_entries) > 10:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, f"Showing 10 of {len(history_entries)} browser history entries. Use full report mode for all items.")
        for h in _report_items(history_entries, report_mode, 10):
            u = h.get("url", "")
            if u in seen_urls:
                continue
            seen_urls.add(u)
            ts = str(h.get("last_accessed") or h.get("last_modified") or "")[:18]
            hits = str(h.get("access_count", 1))
            display_u = u[:75]
            rule_names = ', '.join(rule['name'] for rule in h.get('detection_rules', []))
            pdf.set_x(pdf.l_margin)
            pdf.cell(35, 5, ts, border=1)
            pdf.cell(15, 5, hits, border=1)
            pdf.cell(140, 5, display_u, border=1, new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'I', 9)
        pdf.cell(0, 5, "No high-signal browser history entries recovered.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # 5. Processing Limitations
    add_section_header("Processing Limitations and Errors")
    pdf.set_font('Helvetica', '', 9)
    errors = report.get("errors") or []
    if errors:
        for error in errors:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 5, f"- {error}")
    else:
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 5, "No processing errors were recorded.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # 6. Volume Inventory
    add_section_header("Volume & Artifact Counts Summary")
    pdf.set_font('Helvetica', '', 9)
    counts = [
        ("Total Files Scanned", f"{summary.get('total_files_scanned', 0):,}"),
        ("Deleted Files Recovered", f"{summary.get('total_deleted_found', 0):,}"),
        ("Emails Identified", f"{summary.get('total_emails', 0):,}"),
        ("Documents Identified", f"{summary.get('total_documents', 0):,}"),
        ("Images Identified", f"{summary.get('total_images', 0):,}"),
        ("Registry Hives", f"{summary.get('total_registry_hives', 0):,}"),
        ("Event Logs (.evtx)", f"{summary.get('total_event_logs', 0):,}"),
        ("Browser Artifacts", f"{summary.get('total_browser_artifacts', 0):,}"),
    ]
    for lbl, val in counts:
        pdf.set_x(pdf.l_margin)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(50, 5, f"{lbl}:")
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(0, 5, val, new_x="LMARGIN", new_y="NEXT")

    pdf.output(str(path))
    return str(path)
