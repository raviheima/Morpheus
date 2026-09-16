from typing import Any, Dict, List
import sqlite3
import tempfile
import os
from datetime import datetime, timezone

from app.analysis.base import BaseAnalyzer


class BrowserAnalyzer(BaseAnalyzer):
    """
    Parses browser history databases (Chrome / Edge).
    """

    name = "browser_analyzer"
    description = "Extracts browsing history from Chrome/Edge History SQLite databases"

    def analyze(self, target: str = None, **kwargs) -> Dict[str, Any]:
        """
        Expected kwargs:
            - img_info
            - offset (volume offset)
            - history_files: list of dicts with 'path' of History files found by the scanner
        """
        img_info = kwargs.get("img_info")
        offset = kwargs.get("offset", 0)
        history_files = kwargs.get("history_files", [])

        result = {
            "histories": [],
            "total_entries": 0,
            "errors": [],
        }

        if not history_files:
            return result

        for item in history_files:
            path_in_image = item.get("path")
            if not path_in_image:
                continue

            try:
                entries = self._parse_history(img_info, offset, path_in_image)
                result["histories"].append({
                    "source": path_in_image,
                    "entries": entries,
                    "count": len(entries),
                })
                result["total_entries"] += len(entries)
            except Exception as e:
                result["errors"].append(f"{path_in_image}: {str(e)}")

        return result

    def _parse_history(self, img_info, offset: int, path_in_image: str) -> List[Dict]:
        """Extract a History file from the image and parse it."""
        import pytsk3

        fs = pytsk3.FS_Info(img_info, offset=offset)

        # Normalize path for TSK
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        file_obj = fs.open(path=tsk_path)

        # Write to temporary file
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

            return self._query_history_db(tmp_path)

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _query_history_db(self, db_path: str) -> List[Dict]:
        """Query the Chrome/Edge History SQLite database."""
        entries = []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Chrome/Edge stores time as microseconds since 1601-01-01
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
                # Convert Chrome timestamp to readable format
                try:
                    # Chrome epoch: 1601-01-01
                    timestamp = datetime(1601, 1, 1, tzinfo=timezone.utc) + \
                                __import__("datetime").timedelta(microseconds=visit_time)
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    time_str = str(visit_time)

                entries.append({
                    "url": url,
                    "title": title or "",
                    "visit_count": visit_count,
                    "visit_time": time_str,
                })

        except Exception as e:
            raise Exception(f"SQLite query failed: {e}")
        finally:
            conn.close()

        return entries
