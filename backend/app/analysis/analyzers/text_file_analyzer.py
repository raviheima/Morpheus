from typing import Any, Dict, List, Optional
import re
import pytsk3

from app.analysis.base import BaseAnalyzer


class TextFileAnalyzer(BaseAnalyzer):
    """
    Parses .txt / .TXT files found on a volume.

    Goals (deliberately narrow and factual):
    - Extract a short preview of content
    - Detect known encrypted formats (BCTextEncoder)
    - Flag files that contain common credential / crypto / network indicators
    - Classify location (Documents, Desktop, contact-named folders, Recycle Bin)
    - Never editorialize about the meaning of the content

    The report surfaces facts. Interpretation belongs to the investigator.
    """

    name = "text_file_analyzer"
    description = "Extracts content and indicators from .txt files (previews, BCTextEncoder, credentials, etc.)"

    MAX_READ_BYTES = 64 * 1024
    PREVIEW_CHARS = 600

    BCTEXTENCODER_MARKERS = (
        "-----BEGIN ENCODED MESSAGE-----",
        "-----END ENCODED MESSAGE-----",
        "BCTEXTENCODER",
        "BEGIN ENCODED MESSAGE",
        "END ENCODED MESSAGE",
    )

    EMAIL_RE = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    )
    IPV4_RE = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
        r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    )
    URL_RE = re.compile(
        r"https?://[^\s<>\"']+|www\.[^\s<>\"']+",
        re.IGNORECASE,
    )
    CREDENTIAL_KEYWORDS = {
        "password", "passwd", "pwd", "secret", "token", "api_key",
        "apikey", "private key", "credential", "login", "username",
        "user=", "pass=", "pwd=", "secret=", "token=",
    }

    # Paths that are almost always noise for investigative "Documents of Interest"
    NOISE_PATH_FRAGMENTS = (
        "/appdata/local/temp/",
        "/appdata/local/microsoft/windows/temporary internet files/",
        "/appdata/roaming/openoffice/",
        "/appdata/roaming/libreoffice/",
        "/windows/winsxs/",
        "/program files/",
        "/program files (x86)/",
        "/programdata/",
    )

    def analyze(self, target: str = None, **kwargs) -> Dict[str, Any]:
        img_info = kwargs.get("img_info")
        offset = kwargs.get("offset", 0)
        candidate_files = kwargs.get("text_files", []) or kwargs.get("document_files", [])

        result = {
            "parsed_texts": [],
            "documents_of_interest": [],
            "encrypted_messages": [],
            "total_text_files_parsed": 0,
            "errors": [],
            "skipped": [],
        }

        if not img_info or not candidate_files:
            return result

        try:
            fs = pytsk3.FS_Info(img_info, offset=offset)
        except Exception as e:
            result["errors"].append(f"Failed to open filesystem: {e}")
            return result

        for item in candidate_files:
            path = item.get("path", "")
            name = item.get("name", "")
            size = item.get("size", 0)
            lower_name = name.lower()

            if not lower_name.endswith(".txt"):
                continue

            if size == 0:
                result["skipped"].append({"path": path, "reason": "zero size"})
                continue

            # Windows Recycle Bin $I* files are metadata only (original path + times).
            # Real content lives in the matching $R* entry. Skip $I* for content parsing.
            if self._is_recycle_bin_info_file(path, name):
                result["skipped"].append({"path": path, "reason": "recycle_bin_info_file_$I"})
                continue

            try:
                parsed = self._parse_text_file(fs, path, size, item)
                if not parsed:
                    result["skipped"].append({"path": path, "reason": "could not read"})
                    continue

                result["parsed_texts"].append(parsed)
                result["total_text_files_parsed"] += 1

                if parsed.get("is_encrypted_bctextencoder"):
                    result["encrypted_messages"].append(parsed)
                    result["documents_of_interest"].append(parsed)
                elif parsed.get("is_of_interest"):
                    result["documents_of_interest"].append(parsed)

            except Exception as e:
                result["errors"].append(f"{path}: {e}")

        return result

    def _is_recycle_bin_info_file(self, path: str, name: str) -> bool:
        """True for Windows $Ixxxxxx metadata files inside $Recycle.Bin."""
        p = path.replace("\\", "/").lower()
        n = name.lower()
        if "$recycle.bin" not in p and "/recycler/" not in p:
            return False
        return n.startswith("$i") and n.endswith(".txt")

    def _parse_text_file(
        self,
        fs,
        path_in_image: str,
        size: int,
        meta: Dict,
    ) -> Optional[Dict[str, Any]]:
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        try:
            file_obj = fs.open(path=tsk_path)
            data = file_obj.read_random(0, min(size, self.MAX_READ_BYTES))
        except Exception:
            return None

        text = self._safe_decode(data)
        if text is None:
            return None

        # Normalize for detection: drop NULs that appear when UTF-16 is mis-decoded
        text_clean = text.replace("\x00", "")

        preview = text_clean[: self.PREVIEW_CHARS].strip()
        if len(text_clean) > self.PREVIEW_CHARS:
            preview += " …"

        is_bctext = self._is_bctextencoder(text_clean)
        indicators = self._extract_indicators(text_clean)
        location_class = self._classify_location(path_in_image)
        is_deleted = bool(meta.get("deleted", False))
        is_noise_path = self._is_noise_path(path_in_image)

        is_of_interest = False
        if is_bctext:
            is_of_interest = True
        elif location_class == "recycle_bin" or is_deleted:
            is_of_interest = True
        elif location_class in ("documents", "desktop_contact_folder", "desktop"):
            if not is_noise_path:
                is_of_interest = True
        elif not is_noise_path and (
            bool(indicators.get("credential_keywords"))
            or bool(indicators.get("emails"))
        ):
            is_of_interest = True

        return {
            "path": path_in_image,
            "name": meta.get("name"),
            "size": size,
            "modified": meta.get("modified"),
            "created": meta.get("created"),
            "accessed": meta.get("accessed"),
            "deleted": is_deleted,
            "location_class": location_class,
            "is_encrypted_bctextencoder": is_bctext,
            "encryption_note": (
                "BCTextEncoder format detected — content is encrypted, not decoded"
                if is_bctext
                else None
            ),
            "preview": preview,
            "full_length_chars": len(text_clean),
            "indicators": indicators,
            "is_of_interest": is_of_interest,
        }

    def _safe_decode(self, data: bytes) -> Optional[str]:
        if not data:
            return None

        if data.startswith(b"\xff\xfe"):
            try:
                return data.decode("utf-16-le")
            except Exception:
                pass
        if data.startswith(b"\xfe\xff"):
            try:
                return data.decode("utf-16-be")
            except Exception:
                pass
        if data.startswith(b"\xef\xbb\xbf"):
            try:
                return data.decode("utf-8-sig")
            except Exception:
                pass

        sample = data[:512]
        if sample and (sample.count(b"\x00") / max(len(sample), 1)) > 0.3:
            for enc in ("utf-16-le", "utf-16-be"):
                try:
                    return data.decode(enc)
                except Exception:
                    continue

        for encoding in ("utf-8", "utf-16-le", "utf-16-be", "cp1252", "latin-1"):
            try:
                return data.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                continue

        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return None

    def _is_bctextencoder(self, text: str) -> bool:
        if not text:
            return False
        upper = text.upper()
        collapsed = re.sub(r"\s+", " ", upper)
        return any(
            marker in upper or marker in collapsed
            for marker in self.BCTEXTENCODER_MARKERS
        )

    def _extract_indicators(self, text: str) -> Dict[str, Any]:
        lower = text.lower()
        found_keywords = sorted(
            kw for kw in self.CREDENTIAL_KEYWORDS if kw in lower
        )
        emails = list(dict.fromkeys(self.EMAIL_RE.findall(text)))[:20]
        ips = list(dict.fromkeys(self.IPV4_RE.findall(text)))[:20]
        urls = list(dict.fromkeys(self.URL_RE.findall(text)))[:20]

        return {
            "credential_keywords": found_keywords,
            "emails": emails,
            "ip_addresses": ips,
            "urls": urls,
        }

    def _is_noise_path(self, path: str) -> bool:
        p = path.replace("\\", "/").lower()
        if any(frag in p for frag in self.NOISE_PATH_FRAGMENTS):
            return True
        n = p.split("/")[-1]
        noise_names = (
            "changelog.txt", "readme", "readme.txt", "license.txt",
            "copying.txt", "authors.txt", "install.txt","ContactsLog.txt",
        )
        if any(n.startswith(x) or n == x for x in noise_names):
            if "/documents/" in p or "/my documents/" in p:
                return False
            return True
        if n.startswith("dd_vcredist") or n.startswith("dd_"):
            return True
        return False

    def _classify_location(self, path: str) -> str:
        p = path.replace("\\", "/").lower()

        if "$recycle.bin" in p or "/recycler/" in p or p.endswith("/recycler"):
            return "recycle_bin"

        if "/desktop/" in p:
            after = p.split("/desktop/", 1)[-1]
            parts = [x for x in after.split("/") if x]
            if len(parts) >= 2:
                return "desktop_contact_folder"
            return "desktop"

        if "/documents/" in p or "/my documents/" in p:
            return "documents"

        if "/downloads/" in p:
            return "downloads"

        if "/desktop" in p:
            return "desktop"

        return "other"
