from typing import Any, Dict
from pathlib import PureWindowsPath
import pytsk3

from app.analysis.base import BaseAnalyzer


class FilesystemScanner(BaseAnalyzer):
    """
    Walks a filesystem once and collects high-value forensic artifacts.
    Generic and reusable on any volume (including nested VHDs).
    """

    name = "filesystem_scanner"
    description = "Scans a volume for investigator-relevant artifacts"

    # === Extension & name based rules ===
    VIRTUAL_DISK_EXTS = {".vhd", ".vhdx", ".vmdk"}
    EMAIL_EXTS = {".eml", ".msg", ".pst", ".ost"}
    DOCUMENT_EXTS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt"}
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic"}
    EVENTLOG_EXTS = {".evtx"}
    PREFETCH_EXTS = {".pf"}
    LNK_EXTS = {".lnk"}
    ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
    EXECUTABLE_EXTS = {".exe", ".dll", ".sys", ".bat", ".ps1", ".vbs", ".cmd"}
    DATABASE_EXTS = {".sqlite", ".sqlite3", ".db", ".db3"}

    REGISTRY_NAMES = {
        "ntuser.dat", "sam", "system", "software", "security",
        "default", "usrclass.dat", "components", "bbisystem"
    }

    BROWSER_FILES = {
        "history", "cookies", "login data", "web data", "top sites",
        "favicons", "bookmarks", "places.sqlite", "cookies.sqlite",
        "formhistory.sqlite", "webdata", "logins.json"
    }

    ENCRYPTION_KEYWORDS = {
        "truecrypt", "veracrypt", "bitlocker", "crypt", "encrypted"
    }

    def analyze(self, target: str = None, **kwargs) -> Dict[str, Any]:
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
            "event_logs": [],
            "browser_artifacts": [],
            "prefetch": [],
            "lnk_files": [],
            "jump_lists": [],
            "recycle_bin": [],
            "executables": [],
            "databases": [],
            "archives": [],
            "encryption_related": [],
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
        for entry in directory:
            if entry.info.name.name in [b".", b".."]:
                continue

            try:
                name = entry.info.name.name.decode("utf-8", errors="ignore")
            except Exception:
                continue

            full_path = str(PureWindowsPath(current_path) / name)
            result["total_files_scanned"] += 1
            lower_name = name.lower()
            lower_path = full_path.lower()

            # Directory handling
            if entry.info.meta and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                if lower_name in ["$recycle.bin", "recycler"]:
                    result["recycle_bin"].append({
                        "path": full_path,
                        "name": name,
                        "type": "recycle_bin_folder"
                    })

                # Jump Lists folders
                if "automaticdestinations" in lower_path or "customdestinations" in lower_path:
                    result["jump_lists"].append({
                        "path": full_path,
                        "name": name,
                        "type": "jump_list_folder"
                    })

                try:
                    sub_dir = entry.as_directory()
                    self._walk_directory(fs, sub_dir, full_path, result)
                except Exception:
                    pass
                continue

            # File handling
            self._categorize_file(full_path, name, lower_name, lower_path, entry, result)

    def _categorize_file(self, full_path, name, lower_name, lower_path, entry, result):
        ext = PureWindowsPath(name).suffix.lower()
        size = entry.info.meta.size if entry.info.meta else 0

        file_info = {
            "path": full_path,
            "name": name,
            "size": size,
        }

        # Virtual Disks
        if ext in self.VIRTUAL_DISK_EXTS:
            result["virtual_disks"].append(file_info)
            return

        # Emails
        if ext in self.EMAIL_EXTS:
            result["emails"].append(file_info)
            return

        # Documents
        if ext in self.DOCUMENT_EXTS:
            result["documents"].append(file_info)
            return

        # Images
        if ext in self.IMAGE_EXTS:
            result["images"].append(file_info)
            return

        # Event Logs
        if ext in self.EVENTLOG_EXTS:
            result["event_logs"].append(file_info)
            return

        # Prefetch
        if ext in self.PREFETCH_EXTS:
            result["prefetch"].append(file_info)
            return

        # LNK files
        if ext in self.LNK_EXTS:
            result["lnk_files"].append(file_info)
            return

        # Archives
        if ext in self.ARCHIVE_EXTS:
            result["archives"].append(file_info)
            return

        # Executables
        if ext in self.EXECUTABLE_EXTS:
            result["executables"].append(file_info)
            return

        # Databases
        if ext in self.DATABASE_EXTS:
            result["databases"].append(file_info)
            return

        # Registry Hives
        if lower_name in self.REGISTRY_NAMES or any(h in lower_name for h in self.REGISTRY_NAMES):
            result["registry_hives"].append(file_info)
            return

        # Browser artifacts
        if any(b in lower_name for b in self.BROWSER_FILES) or "chrome" in lower_path or "firefox" in lower_path or "edge" in lower_path:
            result["browser_artifacts"].append(file_info)
            return

        # Encryption related
        if any(k in lower_name for k in self.ENCRYPTION_KEYWORDS):
            result["encryption_related"].append(file_info)
            return

        # Catch interesting leftover files (optional)
        # result["other_interesting"].append(file_info)
