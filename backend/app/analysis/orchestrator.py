from typing import Any, Dict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import pyewf
import pytsk3


ENGINE_VERSION = "1.0.0"

from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo, VHDIImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner
from app.analysis.analyzers.virtual_disk_handler import VirtualDiskHandler
from app.analysis.analyzers.browser_analyzer import BrowserAnalyzer
from app.analysis.analyzers.email_analyzer import EmailAnalyzer
from app.analysis.analyzers.text_file_analyzer import TextFileAnalyzer


class AnalysisOrchestrator:
    """
    High-level orchestrator that runs a full recursive analysis
    on a forensic image (E01, VHD, raw, etc.).
    """

    def __init__(self):
        self.identifier = DataSourceIdentifier()
        self.scanner = FilesystemScanner()
        self.vhd_handler = VirtualDiskHandler()
        self.browser_analyzer = BrowserAnalyzer()
        self.email_analyzer = EmailAnalyzer()
        self.text_file_analyzer = TextFileAnalyzer()

    def analyze(self, target: str) -> Dict[str, Any]:
        path = Path(target)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {target}")

        started_at = datetime.now(timezone.utc)
        report = {
            "report_id": str(uuid4()),
            "target": str(path),
            "engine": {
                "name": "Morpheus Analysis Engine",
                "version": ENGINE_VERSION,
            },
            "analysis_started_at": started_at.isoformat(),
            "analysis_completed_at": None,
            "analysis_duration_seconds": None,
            "status": "running",
            "identification": None,
            "volume_scans": [],
            "nested_virtual_disks": [],
            "summary": {},
            "errors": [],
        }

        try:
            # 1. Identify the data source
            print(f"[+] Identifying: {path.name}")
            identification = self.identifier.analyze(str(path))
            report["identification"] = identification

            # 2. Open the image once
            img_info = self._open_image(path)

            # 3. Process every volume
            for vol in identification.get("volumes", []):
                fs_type = vol.get("filesystem", "Unknown")

                vol_entry = {
                    "description": vol.get("description"),
                    "filesystem": fs_type,
                    "start_sector": vol.get("start_sector"),
                    "size_bytes": vol.get("size_bytes"),
                    "scanned": False,
                    "scan_result": None,
                    "browser_analysis": None,
                    "email_analysis": None,
                    "text_analysis": None,
                    "note": None,
                }

                if fs_type == "Unknown":
                    vol_entry["note"] = "Filesystem could not be determined – skipped deep scan"
                    report["volume_scans"].append(vol_entry)
                    continue

                print(f"[+] Scanning volume: {vol['description']} ({fs_type})")
                offset = vol["start_sector"] * 512

                try:
                    scan = self.scanner.analyze(
                        img_info=img_info,
                        offset=offset,
                        volume_name=vol["description"]
                    )
                    vol_entry["scanned"] = True
                    vol_entry["scan_result"] = scan

                    # Run browser analysis
                    browser_files = scan.get("browser_artifacts", [])
                    if browser_files:
                        print(f"[+] Running browser analysis ({len(browser_files)} artifacts)")
                        browser_result = self.browser_analyzer.analyze(
                            img_info=img_info,
                            offset=offset,
                            history_files=browser_files
                        )
                        vol_entry["browser_analysis"] = browser_result

                    # Run email analysis
                    email_files = scan.get("emails", [])
                    if email_files:
                        print(f"[+] Running email analysis ({len(email_files)} files)")
                        email_result = self.email_analyzer.analyze(
                            img_info=img_info,
                            offset=offset,
                            email_files=email_files
                        )
                        vol_entry["email_analysis"] = email_result

                    # Run text-file analysis (Documents of Interest, BCTextEncoder,
                    # Recycle Bin / deleted .txt, etc.)
                    # Merge documents + any deleted .txt that might not have been
                    # categorized as documents (defensive; scanner usually does both).
                    document_files = list(scan.get("documents", []))
                    seen_paths = {d.get("path") for d in document_files}
                    for deleted in scan.get("deleted_files", []):
                        name = (deleted.get("name") or "").lower()
                        path = deleted.get("path")
                        if name.endswith(".txt") and path and path not in seen_paths:
                            document_files.append(deleted)
                            seen_paths.add(path)

                    if document_files:
                        print(f"[+] Running text-file analysis ({len(document_files)} candidates)")
                        text_result = self.text_file_analyzer.analyze(
                            img_info=img_info,
                            offset=offset,
                            document_files=document_files,
                        )
                        vol_entry["text_analysis"] = text_result

                        # Console summary so findings are visible during a run
                        n_parsed = text_result.get("total_text_files_parsed", 0)
                        doi = text_result.get("documents_of_interest", [])
                        enc = text_result.get("encrypted_messages", [])
                        print(f"    -> Parsed {n_parsed} .txt file(s)")
                        print(f"    -> Documents of Interest: {len(doi)}")
                        print(f"    -> Encrypted (BCTextEncoder): {len(enc)}")
                        for item in doi:
                            loc = item.get("location_class", "other")
                            deleted = " [DELETED]" if item.get("deleted") else ""
                            enc_flag = " [BCTextEncoder]" if item.get("is_encrypted_bctextencoder") else ""
                            print(f"       [{loc}]{deleted}{enc_flag} {item.get('path')}")
                            preview = (item.get("preview") or "").replace("\n", " / ")
                            if preview:
                                print(f"         preview: {preview[:120]}{'…' if len(preview) > 120 else ''}")

                    report["volume_scans"].append(vol_entry)

                    # Handle nested virtual disks
                    for vhd in scan.get("virtual_disks", []):
                        print(f"[+] Found nested VHD: {vhd['path']}")
                        vhd_result = self.vhd_handler.analyze(
                            img_info=img_info,
                            vhd_path=vhd["path"],
                            parent_offset=offset
                        )
                        report["nested_virtual_disks"].append(vhd_result)

                except Exception as e:
                    message = f"Volume {vol.get('description', 'unknown')}: {e}"
                    vol_entry["note"] = f"Scan failed: {e}"
                    report["errors"].append(message)
                    report["volume_scans"].append(vol_entry)

            # 4. Build summary
            report["summary"] = self._build_summary(report)

            completed_at = datetime.now(timezone.utc)
            report["analysis_completed_at"] = completed_at.isoformat()
            report["analysis_duration_seconds"] = round(
                (completed_at - started_at).total_seconds(), 3
            )
            report["status"] = "completed_with_errors" if report["errors"] else "completed"

        except Exception as e:
            completed_at = datetime.now(timezone.utc)
            report["analysis_completed_at"] = completed_at.isoformat()
            report["analysis_duration_seconds"] = round(
                (completed_at - started_at).total_seconds(), 3
            )
            report["status"] = "failed"
            report["errors"].append(str(e))

        return report

    def _open_image(self, path: Path):
        name = path.name.lower()

        if name.endswith((".e01", ".ex01", ".s01")):
            filenames = pyewf.glob(str(path))
            ewf_handle = pyewf.handle()
            ewf_handle.open(filenames)
            return EWFImgInfo(ewf_handle)

        if name.endswith((".vhd", ".vhdx")):
            import pyvhdi
            vhdi_file = pyvhdi.file()
            vhdi_file.open(str(path))
            return VHDIImgInfo(vhdi_file)

        return pytsk3.Img_Info(str(path))

    def _build_summary(self, report: Dict) -> Dict:
        summary = {
            "total_volumes_found": len(report["volume_scans"]),
            "total_volumes_scanned": 0,
            "nested_vhds": len(report["nested_virtual_disks"]),
            "total_files_scanned": 0,
            "total_deleted_found": 0,
            "total_emails": 0,
            "total_emails_parsed": 0,
            "total_email_attachments": 0,
            "total_documents": 0,
            "total_images": 0,
            "total_registry_hives": 0,
            "total_event_logs": 0,
            "total_browser_artifacts": 0,
            "total_browser_history_entries": 0,
            "total_text_files_parsed": 0,
            "total_documents_of_interest": 0,
            "total_encrypted_text_messages": 0,
        }

        for vol in report["volume_scans"]:
            if not vol.get("scanned"):
                continue

            summary["total_volumes_scanned"] += 1
            scan = vol.get("scan_result") or {}

            summary["total_files_scanned"] += scan.get("total_files_scanned", 0)
            summary["total_deleted_found"] += scan.get("total_deleted_found", 0)
            summary["total_emails"] += len(scan.get("emails", []))
            summary["total_documents"] += len(scan.get("documents", []))
            summary["total_images"] += len(scan.get("images", []))
            summary["total_registry_hives"] += len(scan.get("registry_hives", []))
            summary["total_event_logs"] += len(scan.get("event_logs", []))
            summary["total_browser_artifacts"] += len(scan.get("browser_artifacts", []))

            # Browser analysis results
            browser = vol.get("browser_analysis") or {}
            summary["total_browser_history_entries"] += browser.get("total_entries", 0)

            # Email analysis results
            email_res = vol.get("email_analysis") or {}
            summary["total_emails_parsed"] += email_res.get("total_emails_parsed", 0)
            summary["total_email_attachments"] += email_res.get("total_attachments_found", 0)

            # Text-file analysis results
            text_res = vol.get("text_analysis") or {}
            summary["total_text_files_parsed"] += text_res.get("total_text_files_parsed", 0)
            summary["total_documents_of_interest"] += len(text_res.get("documents_of_interest", []))
            summary["total_encrypted_text_messages"] += len(text_res.get("encrypted_messages", []))

        # Nested VHDs
        for vhd in report["nested_virtual_disks"]:
            for scan in vhd.get("scans", []):
                summary["total_files_scanned"] += scan.get("total_files_scanned", 0)
                summary["total_deleted_found"] += scan.get("total_deleted_found", 0)
                summary["total_emails"] += len(scan.get("emails", []))
                summary["total_documents"] += len(scan.get("documents", []))
                summary["total_images"] += len(scan.get("images", []))
                summary["total_registry_hives"] += len(scan.get("registry_hives", []))
                summary["total_event_logs"] += len(scan.get("event_logs", []))
                summary["total_browser_artifacts"] += len(scan.get("browser_artifacts", []))

        return summary
