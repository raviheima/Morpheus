from typing import Any, Dict, List
from pathlib import PureWindowsPath
import pytsk3

from app.analysis.base import BaseAnalyzer


class FilesystemScanner(BaseAnalyzer):
    """
    Walks a filesystem (volume) once and collects interesting findings.
    Designed to be generic and reusable on any NTFS/FAT/etc volume,
    including volumes inside VHDs.
    """

    name = "filesystem_scanner"
    description = "Scans a volume for interesting files and virtual disks"

    # File extensions we care about
    VIRTUAL_DISK_EXTS = {".vhd", ".vhdx", ".vmdk"}
    EMAIL_EXTS = {".eml", ".msg"}
    DOCUMENT_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"}
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"}
    REGISTRY_NAMES = {"ntuser.dat", "sam", "system", "software", "security", "default"}

    def analyze(self, target: str = None, **kwargs) -> Dict[str, Any]:
        """
        target is not used directly.
        We expect these kwargs:
            - img_info: pytsk3.Img_Info
            - offset: byte offset of the volume
            - volume_name: optional label for reporting
        """
        img_info = kwargs.get("img_info")
        offset = kwargs.get("offset", 0)
        volume_name = kwargs.get("volume_name", "unknown")

        if img_info is None:
            raise ValueError("img_info is required")

        result = {
            "volume_name": volume_name,
            "offset": offset,
            "virtual_disks": [],
            "emails": [],
            "documents": [],
            "images": [],
            "registry_hives": [],
            "recycle_bin_items": [],
            "other_interesting": [],
            "total_files_scanned": 0,
            "errors": [],
        }

        try:
            fs = pytsk3.FS_Info(img_info, offset=offset)
            self._walk_directory(fs, fs.open_dir(path="/"), "/", result)
        except Exception as e:
            result["errors"].append(str(e))

        return result

    def _walk_directory(self, fs, directory, current_path: str, result: Dict):
        """Recursively walk the filesystem."""
        for entry in directory:
            if entry.info.name.name in [b".", b".."]:
                continue

            try:
                name = entry.info.name.name.decode("utf-8", errors="ignore")
            except Exception:
                continue

            full_path = str(PureWindowsPath(current_path) / name)
            result["total_files_scanned"] += 1

            # Skip system metadata directories early if needed
            lower_name = name.lower()

            # Check if it's a directory
            if entry.info.meta and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                # Special handling for Recycle Bin
                if lower_name in ["$recycle.bin", "recycler"]:
                    result["recycle_bin_items"].append(full_path)

                try:
                    sub_dir = entry.as_directory()
                    self._walk_directory(fs, sub_dir, full_path, result)
                except Exception:
                    pass
                continue

            # It's a file – categorize it
            self._categorize_file(full_path, name, entry, result)

    def _categorize_file(self, full_path: str, name: str, entry, result: Dict):
        lower_name = name.lower()
        ext = PureWindowsPath(name).suffix.lower()

        file_info = {
            "path": full_path,
            "name": name,
            "size": entry.info.meta.size if entry.info.meta else 0,
        }

        if ext in self.VIRTUAL_DISK_EXTS:
            result["virtual_disks"].append(file_info)

        elif ext in self.EMAIL_EXTS:
            result["emails"].append(file_info)

        elif ext in self.DOCUMENT_EXTS:
            result["documents"].append(file_info)

        elif ext in self.IMAGE_EXTS:
            result["images"].append(file_info)

        elif lower_name in self.REGISTRY_NAMES or lower_name.endswith(".dat"):
            # Simple registry hive detection
            if any(h in lower_name for h in self.REGISTRY_NAMES):
                result["registry_hives"].append(file_info)

        # You can keep expanding categories here later
