from typing import Any, Dict, List
from pathlib import Path
import tempfile
import os
import pytsk3
import pyewf

from app.analysis.base import BaseAnalyzer
from app.analysis.identifier import DataSourceIdentifier, EWFImgInfo
from app.analysis.analyzers.filesystem_scanner import FilesystemScanner


class VirtualDiskHandler(BaseAnalyzer):
    """
    Handles a virtual disk (VHD/VHDX) discovered inside another image.
    Opens it, identifies its volumes, and runs the FilesystemScanner on them.
    Fully recursive and read-only.
    """

    name = "virtual_disk_handler"
    description = "Opens and analyzes virtual disks found inside a parent volume"

    def analyze(self, target: str = None, **kwargs) -> Dict[str, Any]:
        """
        Expected kwargs:
            - img_info: parent pytsk3.Img_Info
            - vhd_path: path of the VHD inside the parent filesystem (e.g. \\Windows\\System32\\config\\SYSTEM.vhd)
            - parent_offset: byte offset of the parent volume
        """
        img_info = kwargs.get("img_info")
        vhd_path = kwargs.get("vhd_path")
        parent_offset = kwargs.get("parent_offset", 0)

        if not img_info or not vhd_path:
            raise ValueError("img_info and vhd_path are required")

        result = {
            "vhd_path": vhd_path,
            "extracted_to": None,
            "identification": None,
            "scans": [],
            "errors": [],
        }

        try:
            # 1. Extract the VHD to a temporary file (read-only usage)
            temp_vhd = self._extract_vhd(img_info, parent_offset, vhd_path)
            result["extracted_to"] = temp_vhd

            # 2. Identify the VHD (same as any other data source)
            identifier = DataSourceIdentifier()
            id_result = identifier.analyze(temp_vhd)
            result["identification"] = id_result

            # 3. Scan every volume inside the VHD
            # 3. Scan every volume that has a recognized filesystem
            scanner = FilesystemScanner()

            # Open the extracted VHD
            if temp_vhd.lower().endswith((".e01", ".ex01")):
                filenames = pyewf.glob(temp_vhd)
                ewf_handle = pyewf.handle()
                ewf_handle.open(filenames)
                vhd_img = EWFImgInfo(ewf_handle)
            else:
                # Use the new VHDI support
                import pyvhdi
                from app.analysis.identifier import VHDIImgInfo
                vhdi_file = pyvhdi.file()
                vhdi_file.open(temp_vhd)
                vhd_img = VHDIImgInfo(vhdi_file)

            for vol in id_result.get("volumes", []):
                fs_type = vol.get("filesystem", "Unknown")

                # Skip volumes we cannot open
                if fs_type == "Unknown" or fs_type is None:
                    continue

                offset = vol["start_sector"] * 512
                scan = scanner.analyze(
                    img_info=vhd_img,
                    offset=offset,
                    volume_name=f"{vhd_path} → {vol['description']} ({fs_type})"
                )
                result["scans"].append(scan)

        except Exception as e:
            result["errors"].append(str(e))

        finally:
            # Clean up temporary file
            if result.get("extracted_to") and os.path.exists(result["extracted_to"]):
                try:
                    os.remove(result["extracted_to"])
                except Exception:
                    pass

        return result

    def _extract_vhd(self, img_info, parent_offset: int, vhd_path: str) -> str:
        """Extract the VHD file from the parent filesystem to a temporary location."""
        fs = pytsk3.FS_Info(img_info, offset=parent_offset)

        # Normalize path for TSK (use forward slashes)
        tsk_path = vhd_path.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        file_obj = fs.open(path=tsk_path)

        # Create a temporary file
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".vhd")
        tmp_path = tmp.name
        tmp.close()

        # Read the entire VHD in chunks and write to temp (read-only source)
        offset = 0
        size = file_obj.info.meta.size
        chunk_size = 1024 * 1024  # 1 MB

        with open(tmp_path, "wb") as out:
            while offset < size:
                data = file_obj.read_random(offset, min(chunk_size, size - offset))
                if not data:
                    break
                out.write(data)
                offset += len(data)

        return tmp_path
