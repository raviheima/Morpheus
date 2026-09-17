from typing import Any, Dict, List, Optional
import sqlite3
import tempfile
import os
import re
import struct
from datetime import datetime, timezone, timedelta
from pathlib import PureWindowsPath

from app.analysis.base import BaseAnalyzer


class BrowserAnalyzer(BaseAnalyzer):
    """
    Parses known browser history formats:
    - Chrome / Edge          → History (SQLite)
    - Firefox                → places.sqlite (noted for now)
    - Internet Explorer:
        • classic index.dat  → pure-Python parser
        • container.dat      → skipped (placeholder on IE10+)
        • WebCacheV*.dat     → full history via pyesedb (ESE)
    """

    name = "browser_analyzer"
    description = "Parses Chrome/Edge History, classic IE index.dat, and modern IE WebCache (ESE)"

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
            "notes": [],
        }

        for item in candidate_files:
            path = item.get("path", "")
            name = item.get("name", "").lower()
            lower_path = path.lower()
            size = item.get("size", 0)

            try:
                # Chrome / Edge History (SQLite)
                if name == "history" and (
                    "chrome" in lower_path
                    or "edge" in lower_path
                    or "user data" in lower_path
                ):
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
                        "size": size,
                    })

                # Classic index.dat (IE 4–9)
                elif name == "index.dat":
                    entries = self._parse_index_dat(img_info, offset, path)
                    result["internet_explorer"].append({
                        "source": path,
                        "type": "index.dat",
                        "entries": entries,
                        "count": len(entries),
                    })
                    result["total_entries"] += len(entries)

                # Modern WebCache ESE (IE10+ / Edge Legacy) – the important one
                elif "webcache" in lower_path and name.endswith(".dat") and "lock" not in name:
                    entries = self._parse_webcache(img_info, offset, path)
                    result["internet_explorer"].append({
                        "source": path,
                        "type": "WebCache ESE",
                        "entries": entries,
                        "count": len(entries),
                        "note": "Parsed with pyesedb (History containers)",
                    })
                    result["total_entries"] += len(entries)
                    if entries:
                        result["notes"].append(
                            f"Extracted {len(entries)} history entries from {path}"
                        )

                # container.dat is a near-always-empty IE10+ placeholder now
                # that WebCacheV*.dat parsing works — skip it entirely.
                elif name == "container.dat" or "history.ie5" in lower_path:
                    result["skipped"].append(path)

                else:
                    result["skipped"].append(path)

            except Exception as e:
                result["errors"].append(f"{path}: {str(e)}")

        return result

    # ------------------------------------------------------------------
    # Chrome / Edge
    # ------------------------------------------------------------------
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
                    data = file_obj.read_random(
                        offset_read, min(chunk_size, size - offset_read)
                    )
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
            SELECT urls.url, urls.title, urls.visit_count, visits.visit_time
            FROM urls
            JOIN visits ON urls.id = visits.url
            ORDER BY visits.visit_time DESC
            LIMIT 500
        """
        try:
            cursor.execute(query)
            for url, title, visit_count, visit_time in cursor.fetchall():
                try:
                    ts = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=visit_time)
                    time_str = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
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

    # ------------------------------------------------------------------
    # Classic index.dat
    # ------------------------------------------------------------------
    def _parse_index_dat(self, img_info, offset: int, path_in_image: str) -> List[Dict]:
        import pytsk3

        fs = pytsk3.FS_Info(img_info, offset=offset)
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        try:
            file_obj = fs.open(path=tsk_path)
            size = file_obj.info.meta.size
            if size == 0 or size > 50 * 1024 * 1024:
                return []
            data = file_obj.read_random(0, size)
        except Exception:
            return []

        return self._extract_index_dat_records(data)

    def _extract_index_dat_records(self, data: bytes) -> List[Dict]:
        entries = []
        sig = b"URL "
        pos = 0
        while True:
            pos = data.find(sig, pos)
            if pos == -1:
                break
            try:
                if pos + 8 > len(data):
                    break
                blocks = struct.unpack_from("<I", data, pos + 4)[0]
                record_len = blocks * 128
                if record_len < 96 or pos + record_len > len(data):
                    pos += 4
                    continue
                record = data[pos:pos + record_len]
                last_mod = self._filetime_to_str(record[8:16])
                last_acc = self._filetime_to_str(record[16:24])
                url = self._extract_url_from_record(record)
                if url:
                    entries.append({
                        "url": url,
                        "last_modified": last_mod,
                        "last_accessed": last_acc,
                        "source_type": "index.dat",
                    })
            except Exception:
                pass
            pos += 4
        return entries

    def _filetime_to_str(self, raw: bytes) -> str:
        try:
            if len(raw) < 8:
                return ""
            val = struct.unpack("<Q", raw)[0]
            if val == 0:
                return ""
            dt = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=val // 10)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return ""

    def _extract_url_from_record(self, record: bytes) -> str:
        try:
            text = record.decode("latin-1", errors="ignore")
        except Exception:
            return ""
        m = re.search(r"Visited:\s*[^@]*@(https?://[^\s\x00]+)", text, re.IGNORECASE)
        if m:
            return m.group(1).rstrip("\x00")
        m = re.search(r"(https?://[^\s\x00]{5,})", text, re.IGNORECASE)
        if m:
            return m.group(1).rstrip("\x00")
        m = re.search(r"(ftp://[^\s\x00]{5,})", text, re.IGNORECASE)
        if m:
            return m.group(1).rstrip("\x00")
        return ""

    # ------------------------------------------------------------------
    # container.dat residual
    # ------------------------------------------------------------------
    def _parse_container_dat(self, img_info, offset: int, path_in_image: str, size: int) -> List[Dict]:
        if size == 0:
            return []
        import pytsk3
        fs = pytsk3.FS_Info(img_info, offset=offset)
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path
        try:
            file_obj = fs.open(path=tsk_path)
            data = file_obj.read_random(0, min(size, 2 * 1024 * 1024))
        except Exception:
            return []
        entries = []
        try:
            text = data.decode("latin-1", errors="ignore")
            for m in re.finditer(r"https?://[^\s\x00\"'<>]{8,200}", text, re.IGNORECASE):
                entries.append({
                    "url": m.group(0).rstrip("\x00"),
                    "last_modified": "",
                    "last_accessed": "",
                    "source_type": "container.dat (residual)",
                })
        except Exception:
            pass
        seen = set()
        unique = []
        for e in entries:
            if e["url"] not in seen:
                seen.add(e["url"])
                unique.append(e)
        return unique[:100]

    # ------------------------------------------------------------------
    # WebCacheV*.dat via pyesedb
    # ------------------------------------------------------------------
    def _parse_webcache(self, img_info, offset: int, path_in_image: str) -> List[Dict]:
        try:
            import pyesedb
        except ImportError:
            return [{
                "url": "",
                "note": "pyesedb not installed. Run: pip install libesedb-python",
                "source_type": "WebCache ESE (missing dependency)",
            }]

        import pytsk3
        fs = pytsk3.FS_Info(img_info, offset=offset)
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        try:
            file_obj = fs.open(path=tsk_path)
            size = file_obj.info.meta.size
            if size == 0:
                return []

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dat")
            tmp_path = tmp.name
            tmp.close()

            offset_read = 0
            chunk_size = 1024 * 1024
            with open(tmp_path, "wb") as out:
                while offset_read < size:
                    data = file_obj.read_random(offset_read, min(chunk_size, size - offset_read))
                    if not data:
                        break
                    out.write(data)
                    offset_read += len(data)
        except Exception as e:
            return [{"url": "", "note": f"Failed to extract WebCache: {e}", "source_type": "WebCache ESE"}]

        try:
            return self._extract_webcache_history(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def _extract_webcache_history(self, db_path: str) -> List[Dict]:
        """Parse History / MSHist containers from WebCacheV*.dat using known schema."""
        import pyesedb

        entries: List[Dict] = []
        diagnostics: List[str] = []
        esedb_file = pyesedb.file()

        try:
            esedb_file.open(db_path)
        except Exception as e:
            return [{"url": "", "note": f"pyesedb open failed: {e}", "source_type": "WebCache ESE"}]

        try:
            containers_table = esedb_file.get_table_by_name("Containers")
            if not containers_table:
                return [{"url": "", "note": "No 'Containers' table found", "source_type": "WebCache ESE"}]

            num_containers = containers_table.get_number_of_records()
            diagnostics.append(f"Containers table has {num_containers} records")

            history_container_ids: List[int] = []
            all_container_info: List[str] = []

            for i in range(num_containers):
                try:
                    record = containers_table.get_record(i)

                    container_id = (
                        self._get_ese_value(record, 0, as_int=True)
                        or self._get_ese_value(record, "ContainerId", as_int=True)
                    )

                    name = (
                        self._get_ese_value(record, "Name")
                        or self._get_ese_value(record, 8)
                        or ""
                    )
                    directory = (
                        self._get_ese_value(record, "Directory")
                        or self._get_ese_value(record, 10)
                        or ""
                    )

                    name_l = str(name).lower()
                    dir_l = str(directory).lower()

                    all_container_info.append(
                        f"id={container_id} name='{name}' dir='{str(directory)[:50]}'"
                    )

                    if (
                        name_l == "history"
                        or name_l.startswith("mshist")
                        or "history.ie5" in dir_l
                        or "mshist" in dir_l
                    ):
                        if container_id is not None:
                            history_container_ids.append(container_id)

                except Exception as e:
                    diagnostics.append(f"Error reading container record {i}: {e}")
                    continue

            diagnostics.append(
                f"Found {len(history_container_ids)} History/MSHist containers: {history_container_ids}"
            )
            diagnostics.append("All containers: " + " | ".join(all_container_info[:12]))

            for cid in history_container_ids:
                table_name = f"Container_{cid}"
                try:
                    table = esedb_file.get_table_by_name(table_name)
                    if not table:
                        diagnostics.append(f"Table {table_name} not found")
                        continue

                    num_recs = table.get_number_of_records()
                    diagnostics.append(f"{table_name} has {num_recs} records")

                    column_names = self._get_table_column_names(table)
                    time_columns = [
                        (idx, cname) for idx, cname in enumerate(column_names)
                        if cname and "time" in cname.lower()
                    ]
                    url_columns = [
                        (idx, cname) for idx, cname in enumerate(column_names)
                        if cname and cname.lower() == "url"
                    ]
                    if j_debug := (num_recs > 0):
                        diagnostics.append(
                            f"{table_name} columns: {column_names}"
                        )

                    for j in range(num_recs):
                        try:
                            rec = table.get_record(j)

                            # ---- URL ----
                            url = None
                            for idx, cname in url_columns:
                                url = (
                                    self._get_ese_long_value(rec, cname)
                                    or self._get_ese_value(rec, idx)
                                )
                                if url:
                                    break
                            if not url:
                                url = (
                                    self._get_ese_long_value(rec, "Url")
                                    or self._get_ese_value(rec, 17)
                                )

                            if not url or not isinstance(url, str) or len(url) < 8:
                                continue

                            url = self._clean_webcache_url(url)
                            if not url or len(url) < 8:
                                continue

                            # ---- Timestamps ----
                            accessed = ""
                            modified = ""
                            for idx, cname in time_columns:
                                cname_l = cname.lower()
                                ts = self._get_ese_filetime(rec, idx)
                                if not ts:
                                    continue
                                if "access" in cname_l and not accessed:
                                    accessed = ts
                                elif "modif" in cname_l and not modified:
                                    modified = ts
                                elif "sync" in cname_l and not accessed:
                                    accessed = ts
                                elif "creat" in cname_l and not modified:
                                    modified = ts
                                elif not accessed:
                                    accessed = ts
                                elif not modified:
                                    modified = ts

                            # ---- AccessCount ----
                            access_count = self._get_ese_access_count(rec)

                            entries.append({
                                "url": url,
                                "last_accessed": accessed,
                                "last_modified": modified,
                                "access_count": access_count,
                                "source_type": f"WebCache Container_{cid}",
                            })
                        except Exception:
                            continue

                except Exception as e:
                    diagnostics.append(f"Error processing {table_name}: {e}")

        finally:
            esedb_file.close()

        if not entries:
            return [{
                "url": "",
                "note": " | ".join(diagnostics),
                "source_type": "WebCache ESE (diagnostics)",
            }]

        # Deduplicate by URL, keep the most recent access
        seen: Dict[str, Dict] = {}
        for e in entries:
            u = e["url"]
            if u not in seen or (e.get("last_accessed") or "") > (seen[u].get("last_accessed") or ""):
                seen[u] = e

        return list(seen.values())[:1000]

    # ------------------------------------------------------------------
    # ESE helpers
    # ------------------------------------------------------------------
    def _get_table_column_names(self, table) -> List[Optional[str]]:
        """Return the real column names for an ESE table, in column order."""
        names: List[Optional[str]] = []
        try:
            num_cols = table.get_number_of_columns()
        except Exception:
            return names
        for i in range(num_cols):
            try:
                col = table.get_column(i)
                names.append(col.get_name())
            except Exception:
                names.append(None)
        return names

    def _clean_webcache_url(self, raw: str) -> str:
        """Strip Visited: prefixes, user@, and MSHist date-range prefixes."""
        url = raw.strip().rstrip("\x00")

        # MSHist form often starts with ":2014021020140217: Jimmy Wilson@https://..."
        m = re.match(r"^:?\d{8,16}:\s*", url)
        if m:
            url = url[m.end():].strip()

        # "Visited: username@http..." or just "username@http..."
        if "@" in url and any(p in url.lower() for p in ("http://", "https://", "file://", "ftp://")):
            url = url.split("@", 1)[-1]

        if url.lower().startswith("visited:"):
            url = url.split(":", 1)[-1].strip()

        m = re.match(r"^\d{8,16}:\s*(https?://.+|file://.+|ftp://.+)", url, re.IGNORECASE)
        if m:
            url = m.group(1)

        url = url.strip().rstrip("\x00")
        if not url.lower().startswith(("http://", "https://", "file://", "ftp://")):
            return ""
        return url

    def _debug_webcache_record(self, record, max_cols: int = 22) -> str:
        """Dump raw column values (with FILETIME detection) for debugging."""
        info = []
        for i in range(max_cols):
            try:
                val = record.get_value_data(i)
                if val is None:
                    continue
                if isinstance(val, bytes):
                    if len(val) == 8:
                        try:
                            ft = struct.unpack("<Q", val)[0]
                            if 100_000_000_000_000_000 < ft < 200_000_000_000_000_000:
                                dt = (
                                    datetime(1601, 1, 1, tzinfo=timezone.utc)
                                    + timedelta(microseconds=ft // 10)
                                )
                                val = f"FILETIME → {dt.strftime('%Y-%m-%d %H:%M:%S')}"
                            else:
                                val = f"0x{ft:x}" if ft < 0x100000000 else val.hex()
                        except Exception:
                            val = val.hex()
                    else:
                        try:
                            val = val.decode("utf-16-le", errors="ignore").rstrip("\x00")[:80]
                        except Exception:
                            val = val.hex()[:40]
                info.append(f"[{i}]={val}")
            except Exception:
                continue
        return " | ".join(info)

    def _get_ese_access_count(self, record) -> int:
        """Read AccessCount robustly as unsigned integer."""
        try:
            try:
                v = record.get_value_data_as_integer_by_name("AccessCount")
                if v is not None and v >= 0:
                    return int(v)
            except Exception:
                pass
            try:
                v = record.get_value_data_as_integer(8)
                if v is not None and v >= 0:
                    return int(v)
            except Exception:
                pass
            try:
                raw = record.get_value_data(8)
                if isinstance(raw, bytes) and len(raw) >= 1:
                    return int.from_bytes(raw[:4] if len(raw) >= 4 else raw, "little")
            except Exception:
                pass
        except Exception:
            pass
        return 0

    def _get_ese_value(self, record, key, as_int: bool = False) -> Optional[Any]:
        try:
            if isinstance(key, int):
                val = record.get_value_data(key)
            else:
                try:
                    val = record.get_value_data_by_name(key)
                except Exception:
                    return None
            if val is None:
                return None
            if as_int:
                try:
                    if isinstance(key, int):
                        return record.get_value_data_as_integer(key)
                    return record.get_value_data_as_integer_by_name(key)
                except Exception:
                    try:
                        return int.from_bytes(val, "little") if isinstance(val, bytes) else int(val)
                    except Exception:
                        return None
            if isinstance(val, bytes):
                try:
                    return val.decode("utf-16-le", errors="ignore").rstrip("\x00")
                except Exception:
                    try:
                        return val.decode("utf-8", errors="ignore").rstrip("\x00")
                    except Exception:
                        return val.hex()
            return val
        except Exception:
            return None

    def _get_ese_long_value(self, record, name: str) -> Optional[str]:
        try:
            long_val = None
            try:
                long_val = record.get_value_data_as_long_value_by_name(name)
            except Exception:
                pass
            if long_val is None and name.lower() == "url":
                try:
                    long_val = record.get_value_data_as_long_value(17)
                except Exception:
                    pass
            if long_val is None:
                return None
            data = long_val.get_data()
            if not data:
                return None
            try:
                return data.decode("utf-16-le", errors="ignore").rstrip("\x00")
            except Exception:
                return data.decode("utf-8", errors="ignore").rstrip("\x00")
        except Exception:
            return None

    def _get_ese_filetime(self, record, key) -> str:
        """Robust FILETIME extractor – prefer raw 8-byte little-endian value."""
        try:
            raw = None
            if isinstance(key, int):
                try:
                    raw = record.get_value_data(key)
                except Exception:
                    pass
            else:
                try:
                    raw = record.get_value_data_by_name(key)
                except Exception:
                    pass

            val = None
            if isinstance(raw, bytes) and len(raw) >= 8:
                val = struct.unpack("<Q", raw[:8])[0]
            elif isinstance(raw, int):
                val = raw
            else:
                try:
                    if isinstance(key, int):
                        val = record.get_value_data_as_integer(key)
                    else:
                        val = record.get_value_data_as_integer_by_name(key)
                except Exception:
                    return ""

            if not val or val < 100_000_000_000_000_000:
                return ""

            dt = datetime(1601, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=val // 10)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return ""
