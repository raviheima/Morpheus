from typing import Any, Dict
from pathlib import PureWindowsPath
import pytsk3

from app.analysis.base import BaseAnalyzer


class FilesystemScanner(BaseAnalyzer):
    """
    Walks a filesystem once and collects high-value forensic artifacts,
    including deleted files, suspicious files, and basic timestamps.
    """

    name = "filesystem_scanner"
    description = "Scans a volume for investigator-relevant artifacts (including deleted & suspicious files)"

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

    SUSPICIOUS_EXTENSIONS = {
        ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".jse",
        ".scr", ".pif", ".msi", ".com", ".hta", ".wsf", ".wsh"
    }

    SUSPICIOUS_KEYWORDS = {
        "password", "credential", "secret", "private", "backup", "dump",
        "mimikatz", "lazagne", "keylog", "stealer", "rat", "payload",
        "reverse", "shell", "meterpreter", "cobalt", "beacon"
    }

    DOUBLE_EXTENSIONS = {
        ".pdf.exe", ".doc.exe", ".docx.exe", ".xls.exe",
        ".xlsx.exe", ".jpg.exe", ".png.exe", ".txt.exe"
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
            "deleted_files": [],
            "suspicious_files": [],
            "other_interesting": [],
            "total_files_scanned": 0,
            "total_deleted_found": 0,
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

            # Check if deleted / unallocated
            is_deleted = False
            try:
                if entry.info.name.flags & pytsk3.TSK_FS_NAME_FLAG_UNALLOC:
                    is_deleted = True
            except Exception:
                pass

            # Directory handling
            if entry.info.meta and entry.info.meta.type == pytsk3.TSK_FS_META_TYPE_DIR:
                if lower_name in ["$recycle.bin", "recycler"]:
                    result["recycle_bin"].append({
                        "path": full_path,
                        "name": name,
                        "type": "recycle_bin_folder",
                        "deleted": is_deleted
                    })

                if "automaticdestinations" in lower_path or "customdestinations" in lower_path:
                    result["jump_lists"].append({
                        "path": full_path,
                        "name": name,
                        "type": "jump_list_folder",
                        "deleted": is_deleted
                    })

                try:
                    sub_dir = entry.as_directory()
                    self._walk_directory(fs, sub_dir, full_path, result)
                except Exception:
                    pass
                continue

            # File handling
            self._categorize_file(
                full_path, name, lower_name, lower_path,
                entry, result, is_deleted
            )

    def _categorize_file(self, full_path, name, lower_name, lower_path, entry, result, is_deleted):
        ext = PureWindowsPath(name).suffix.lower()
        size = entry.info.meta.size if entry.info.meta else 0

        # Extract timestamps
        created = modified = accessed = None
        try:
            if entry.info.meta:
                if entry.info.meta.crtime:
                    created = entry.info.meta.crtime
                if entry.info.meta.mtime:
                    modified = entry.info.meta.mtime
                if entry.info.meta.atime:
                    accessed = entry.info.meta.atime
        except Exception:
            pass

        file_info = {
            "path": full_path,
            "name": name,
            "size": size,
            "deleted": is_deleted,
            "created": created,
            "modified": modified,
            "accessed": accessed,
        }

        if is_deleted:
            result["deleted_files"].append(file_info)
            result["total_deleted_found"] += 1

        # === Suspicious file detection ===
        is_suspicious = False
        reasons = []

        if any(full_path.lower().endswith(de) for de in self.DOUBLE_EXTENSIONS):
            is_suspicious = True
            reasons.append("double_extension")

        if any(k in lower_name for k in self.SUSPICIOUS_KEYWORDS):
            is_suspicious = True
            reasons.append("suspicious_keyword")

        unusual_locations = [
            "\\users\\", "\\documents\\", "\\downloads\\",
            "\\desktop\\", "\\temp\\", "\\tmp\\", "\\recycle"
        ]
        if ext in self.SUSPICIOUS_EXTENSIONS and any(loc in lower_path for loc in unusual_locations):
            is_suspicious = True
            reasons.append("executable_in_user_location")

        if any(k in lower_name for k in self.ENCRYPTION_KEYWORDS):
            is_suspicious = True
            reasons.append("encryption_related")
            result["encryption_related"].append(file_info)

        if is_suspicious:
            suspicious_info = file_info.copy()
            suspicious_info["reasons"] = reasons
            result["suspicious_files"].append(suspicious_info)

        # === Normal categorization ===
        if ext in self.VIRTUAL_DISK_EXTS:
            result["virtual_disks"].append(file_info)
            return

        if ext in self.EMAIL_EXTS:
            result["emails"].append(file_info)
            return

        if ext in self.DOCUMENT_EXTS:
            result["documents"].append(file_info)
            return

        if ext in self.IMAGE_EXTS:
            result["images"].append(file_info)
            return

        if ext in self.EVENTLOG_EXTS:
            result["event_logs"].append(file_info)
            return

        if ext in self.PREFETCH_EXTS:
            result["prefetch"].append(file_info)
            return

        if ext in self.LNK_EXTS:
            result["lnk_files"].append(file_info)
            return

        if ext in self.ARCHIVE_EXTS:
            result["archives"].append(file_info)
            return

        if ext in self.EXECUTABLE_EXTS:
            result["executables"].append(file_info)
            return

        if ext in self.DATABASE_EXTS:
            result["databases"].append(file_info)
            return

        if lower_name in self.REGISTRY_NAMES or any(h in lower_name for h in self.REGISTRY_NAMES):
            result["registry_hives"].append(file_info)
            return

        # === Browser Artifacts (more precise) ===
        is_browser_artifact = False

        # Chrome / Edge History database
        if lower_name == "history" and ("chrome" in lower_path or "edge" in lower_path or "user data" in lower_path):
            is_browser_artifact = True

        # Firefox
        elif lower_name == "places.sqlite" and "firefox" in lower_path:
            is_browser_artifact = True

        # Internet Explorer / old Edge
        elif any(x in lower_path for x in [
            "temporary internet files",
            "content.ie5",
            "webbrowse",
            "webcache",
            "history.ie5",
            "index.dat"
        ]):
            is_browser_artifact = True

        # General browser files we already had
        elif any(b in lower_name for b in self.BROWSER_FILES) or \
             "chrome" in lower_path or "firefox" in lower_path or "edge" in lower_path:
            is_browser_artifact = True

        if is_browser_artifact:
            result["browser_artifacts"].append(file_info)
            return
