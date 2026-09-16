from typing import Any, Dict
from pathlib import Path
import pyewf
import pytsk3

from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo, VHDIImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner
from app.analysis.analyzers.virtual_disk_handler import VirtualDiskHandler


class AnalysisOrchestrator:
    """
    High-level orchestrator that runs a full recursive analysis
    on a forensic image (E01, VHD, raw, etc.).
    """

    def __init__(self):
        self.identifier = DataSourceIdentifier()
        self.scanner = FilesystemScanner()
        self.vhd_handler = VirtualDiskHandler()

    def analyze(self, target: str) -> Dict[str, Any]:
        path = Path(target)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {target}")

        report = {
            "target": str(path),
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
                    report["volume_scans"].append(vol_entry)

                    # Handle nested virtual disks (only once)
                    for vhd in scan.get("virtual_disks", []):
                        print(f"[+] Found nested VHD: {vhd['path']}")
                        vhd_result = self.vhd_handler.analyze(
                            img_info=img_info,
                            vhd_path=vhd["path"],
                            parent_offset=offset
                        )
                        report["nested_virtual_disks"].append(vhd_result)

                except Exception as e:
                    vol_entry["note"] = f"Scan failed: {e}"
                    report["volume_scans"].append(vol_entry)

            # 4. Build summary
            report["summary"] = self._build_summary(report)

        except Exception as e:
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
            "total_emails": 0,
            "total_documents": 0,
            "total_images": 0,
            "total_registry_hives": 0,
            "total_event_logs": 0,
            "total_browser_artifacts": 0,
        }

        for vol in report["volume_scans"]:
            if not vol.get("scanned"):
                continue

            summary["total_volumes_scanned"] += 1
            scan = vol.get("scan_result") or {}

            summary["total_files_scanned"] += scan.get("total_files_scanned", 0)
            summary["total_emails"] += len(scan.get("emails", []))
            summary["total_documents"] += len(scan.get("documents", []))
            summary["total_images"] += len(scan.get("images", []))
            summary["total_registry_hives"] += len(scan.get("registry_hives", []))
            summary["total_event_logs"] += len(scan.get("event_logs", []))
            summary["total_browser_artifacts"] += len(scan.get("browser_artifacts", []))

        # Nested VHDs
        for vhd in report["nested_virtual_disks"]:
            for scan in vhd.get("scans", []):
                summary["total_files_scanned"] += scan.get("total_files_scanned", 0)
                summary["total_emails"] += len(scan.get("emails", []))
                summary["total_documents"] += len(scan.get("documents", []))
                summary["total_images"] += len(scan.get("images", []))
                summary["total_registry_hives"] += len(scan.get("registry_hives", []))
                summary["total_event_logs"] += len(scan.get("event_logs", []))
                summary["total_browser_artifacts"] += len(scan.get("browser_artifacts", []))

        return summary
