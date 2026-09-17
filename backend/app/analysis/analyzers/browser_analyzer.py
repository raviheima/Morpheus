from typing import Any, Dict, List
import sqlite3
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import PureWindowsPath

from app.analysis.base import BaseAnalyzer


class BrowserAnalyzer(BaseAnalyzer):
    """
    Only attempts to parse browser history files we actually know how to handle:
    - Chrome / Edge  → History (SQLite)
    - Firefox        → places.sqlite
    - Internet Explorer → container.dat / index.dat (listed for now)
    """

    name = "browser_analyzer"
    description = "Parses only known browser history formats"

    def analyze(self, target: str = None, **kwargs) -> Dict[str, Any]:
        img_info = kwargs.get("img_info")
        offset = kwargs.get("offset", 0)
        candidate_files = kwargs.get("history_files", [])

        result = {
            "chrome_edge": [],
            "firefox": [],
            "internet_explorer": [],
            "total_entries": 0,
            "errors": [],
            "skipped": [],
        }

        for item in candidate_files:
            path = item.get("path", "")
            name = item.get("name", "").lower()
            lower_path = path.lower()

            try:
                # Chrome / Edge History (SQLite)
                if name == "history" and ("chrome" in lower_path or "edge" in lower_path or "user data" in lower_path):
                    entries = self._parse_chrome_history(img_info, offset, path)
                    result["chrome_edge"].append({
                        "source": path,
                        "entries": entries,
                        "count": len(entries),
                    })
                    result["total_entries"] += len(entries)

                # Firefox
                elif name == "places.sqlite":
                    result["firefox"].append({
                        "source": path,
                        "note": "Firefox places.sqlite detected (parser not yet implemented)",
                        "size": item.get("size"),
                    })

                # Internet Explorer
                elif name in ["container.dat", "index.dat"] or "history.ie5" in lower_path:
                    result["internet_explorer"].append({
                        "source": path,
                        "note": "Internet Explorer history artifact detected",
                        "size": item.get("size"),
                    })

                else:
                    # Not a format we can parse → skip
                    result["skipped"].append(path)

            except Exception as e:
                result["errors"].append(f"{path}: {str(e)}")

        return result

    def _parse_chrome_history(self, img_info, offset: int, path_in_image: str) -> List[Dict]:
        import pytsk3

        fs = pytsk3.FS_Info(img_info, offset=offset)
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        file_obj = fs.open(path=tsk_path)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        tmp_path = tmp.name
        tmp.close()

        try:
            size = file_obj.info.meta.size
            offset_read = 0
            chunk_size = 1024 * 1024

            with open(tmp_path, "wb") as out:
                while offset_read < size:
                    data = file_obj.read_random(offset_read, min(chunk_size, size - offset_read))
                    if not data:
                        break
                    out.write(data)
                    offset_read += len(data)

            return self._query_chrome_db(tmp_path)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _query_chrome_db(self, db_path: str) -> List[Dict]:
        entries = []
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        query = """
            SELECT
                urls.url,
                urls.title,
                urls.visit_count,
                visits.visit_time
            FROM urls
            JOIN visits ON urls.id = visits.url
            ORDER BY visits.visit_time DESC
            LIMIT 500
        """

        try:
            cursor.execute(query)
            rows = cursor.fetchall()

            for url, title, visit_count, visit_time in rows:
                try:
                    timestamp = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=visit_time)
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    time_str = str(visit_time)

                entries.append({
                    "url": url,
                    "title": title or "",
                    "visit_count": visit_count,
                    "visit_time": time_str,
                })
        finally:
            conn.close()

        return entries
