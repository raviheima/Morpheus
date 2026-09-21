"""UI presentation from orchestrator report (full lists where present)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any


def _list(v: Any) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _uniq(items: list[dict], keys: tuple[str, ...]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        k = next((str(it[x]) for x in keys if it.get(x)), None)
        if k is None:
            k = str(id(it))
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out


def build_presentation(report: dict) -> dict:
    if not isinstance(report, dict):
        report = {}

    # Prefer official presentation exporter (same as test_orchestrator)
    try:
        from app.analysis.report import export_report_json

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", prefix="mz_pres_", delete=False, encoding="utf-8"
        ) as tmp:
            path = tmp.name
        export_report_json(report, path, presentation_only=True)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        Path(path).unlink(missing_ok=True)
        if isinstance(data, dict) and data.get("case_summary"):
            # Enrich with full volume lists if exporter only sampled
            enriched = _from_volumes(report)
            for key in (
                "documents_of_interest",
                "suspicious_files",
                "deleted_files",
                "sample_emails",
                "sample_web_history",
                "images",
            ):
                if len(enriched.get(key) or []) > len(data.get(key) or []):
                    data[key] = enriched[key]
            data.setdefault("nested_virtual_disks", report.get("nested_virtual_disks") or [])
            return data
    except Exception:
        pass

    return _from_volumes(report)


def _from_volumes(report: dict) -> dict:
    summary = report.get("summary") or {}
    ident = report.get("identification") or {}
    nested = report.get("nested_virtual_disks") or []

    emails: list[dict] = []
    history: list[dict] = []
    docs_interest: list[dict] = []
    suspicious: list[dict] = []
    deleted: list[dict] = []
    images: list[dict] = []

    for vol in report.get("volume_scans") or []:
        if not isinstance(vol, dict):
            continue

        # --- Emails ---
        ea = vol.get("email_analysis") or {}
        if isinstance(ea, dict):
            for em in _list(ea.get("parsed_emails")):
                if isinstance(em, dict):
                    emails.append(em)

        # --- Browser history ---
        ba = vol.get("browser_analysis") or {}
        if isinstance(ba, dict):
            for bucket in ("internet_explorer", "chrome_edge", "firefox"):
                for block in _list(ba.get(bucket)):
                    if not isinstance(block, dict):
                        continue
                    for entry in _list(block.get("entries")):
                        if not isinstance(entry, dict):
                            continue
                        row = dict(entry)
                        if row.get("access_count") is None and row.get("visit_count") is not None:
                            row["access_count"] = row["visit_count"]
                        history.append(row)

        # --- Text / documents of interest ---
        ta = vol.get("text_analysis") or {}
        if isinstance(ta, dict):
            for key in (
                "documents_of_interest",
                "encrypted_messages",
                "encrypted",
                "encrypted_files",
                "interesting",
                "interesting_documents",
                "parsed_texts",
                "documents",
            ):
                for doc in _list(ta.get(key)):
                    if isinstance(doc, dict):
                        docs_interest.append(doc)

        # --- scan_result inventory ---
        sr = vol.get("scan_result") or {}
        if isinstance(sr, dict):
            for s in _list(sr.get("suspicious_files")):
                if isinstance(s, dict):
                    suspicious.append(s)
            for d in _list(sr.get("deleted_files")) + _list(sr.get("deleted")):
                if isinstance(d, dict):
                    deleted.append(d)
            for d in _list(sr.get("documents")) + _list(sr.get("other_interesting")):
                if isinstance(d, dict):
                    # interest-ish docs may also appear here
                    if d.get("reasons") or "interest" in str(d.get("type", "")).lower():
                        docs_interest.append(d)
            for im in _list(sr.get("images")):
                if isinstance(im, dict):
                    images.append(im)
            for em in _list(sr.get("emails")):
                if isinstance(em, dict) and (em.get("from") or em.get("subject")):
                    emails.append(em)

    # Nested VHD suspicious / images
    for vhd in nested:
        if not isinstance(vhd, dict):
            continue
        for scan in _list(vhd.get("scans")):
            if not isinstance(scan, dict):
                continue
            for s in _list(scan.get("suspicious_files")):
                if isinstance(s, dict):
                    suspicious.append({**s, "source": "nested_vhd"})
            for im in _list(scan.get("images")):
                if isinstance(im, dict):
                    images.append(im)

    # Tag recycle paths as deleted if not already
    for d in docs_interest:
        p = str(d.get("path") or "")
        if "RECYCLE" in p.upper() or d.get("deleted"):
            deleted.append(d)

    emails = _uniq(emails, ("message_id", "source_path", "subject", "from"))
    history = _uniq(history, ("url", "last_accessed"))
    docs_interest = _uniq(docs_interest, ("path", "name"))
    suspicious = _uniq(suspicious, ("path", "name"))
    deleted = _uniq(deleted, ("path", "name"))
    images = _uniq(images, ("path", "name"))

    case_summary = {
        "target": report.get("target") or ident.get("file_path"),
        "image_type": ident.get("image_type") or "Unknown",
        "is_operating_system": bool(ident.get("is_operating_system")),
        "total_files_scanned": summary.get("total_files_scanned") or 0,
        "total_deleted_recovered": summary.get("total_deleted_found") or 0,
        "total_emails_parsed": summary.get("total_emails_parsed")
        or summary.get("total_emails")
        or len(emails),
        "total_browser_history_entries": summary.get("total_browser_history_entries")
        or len(history),
        "total_documents_of_interest": summary.get("total_documents_of_interest")
        or len(docs_interest),
        "total_suspicious": len(suspicious),
        "total_images": summary.get("total_images") or len(images),
    }

    return {
        "case_summary": case_summary,
        "documents_of_interest": docs_interest,
        "suspicious_files": suspicious,
        "deleted_files": deleted,
        "sample_emails": emails,
        "sample_web_history": history,
        "images": images,
        "nested_virtual_disks": nested,
        "errors": report.get("errors") or [],
        "_raw_summary": summary,
        "_identification": ident,
    }
