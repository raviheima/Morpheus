from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Set

from app.database import SessionLocal, DataSource, Case, ChainOfCustody


class CaseFileWatcher:
    """
    Lightweight poll-based watcher for registered data-source paths.
    If a file disappears or its size/mtime changes, log a custody warning
    and mark the data source inconsistent.

    (Poll-based so we don't require watchdog as a hard dependency.
     Swap to watchdog later if you want instant events.)
    """

    def __init__(self, interval_seconds: int = 30):
        self.interval = interval_seconds
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # path -> (size, mtime, data_source_id, case_id)
        self._snapshot: Dict[str, tuple] = {}

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._refresh_snapshot()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="CaseFileWatcher", daemon=True)
        self._thread.start()
        print(f"[watcher] started (interval={self.interval}s, watching {len(self._snapshot)} paths)")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        print("[watcher] stopped")

    def _refresh_snapshot(self):
        db = SessionLocal()
        try:
            rows = db.query(DataSource).all()
            snap = {}
            for ds in rows:
                p = Path(ds.stored_path)
                if p.exists():
                    st = p.stat()
                    snap[ds.stored_path] = (st.st_size, st.st_mtime, ds.id, ds.case_id)
                else:
                    snap[ds.stored_path] = (None, None, ds.id, ds.case_id)
            self._snapshot = snap
        finally:
            db.close()

    def _loop(self):
        while not self._stop.wait(self.interval):
            try:
                self._tick()
            except Exception as exc:
                print(f"[watcher] error: {exc}")

    def _tick(self):
        # reload registry in case new data sources were added
        self._refresh_snapshot()

        db = SessionLocal()
        try:
            for path_str, (old_size, old_mtime, ds_id, case_id) in list(self._snapshot.items()):
                path = Path(path_str)
                ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
                if not ds:
                    continue

                if not path.exists():
                    if ds.is_consistent:
                        msg = f"Data source missing: {path_str}"
                        print(f"[watcher] WARNING: {msg}")
                        ds.is_consistent = False
                        ds.last_warning = msg
                        db.add(
                            ChainOfCustody(
                                case_id=case_id,
                                data_source_id=ds_id,
                                action="data_source_warning",
                                actor="watcher",
                                details=json.dumps({"warning": msg, "path": path_str}),
                            )
                        )
                    continue

                st = path.stat()
                if old_size is not None and (st.st_size != old_size or st.st_mtime != old_mtime):
                    msg = (
                        f"Data source changed on disk (size/mtime). "
                        f"Path={path_str}. Run integrity check to confirm."
                    )
                    print(f"[watcher] WARNING: {msg}")
                    ds.is_consistent = False
                    ds.last_warning = msg
                    db.add(
                        ChainOfCustody(
                            case_id=case_id,
                            data_source_id=ds_id,
                            action="data_source_warning",
                            actor="watcher",
                            details=json.dumps(
                                {
                                    "warning": msg,
                                    "path": path_str,
                                    "old_size": old_size,
                                    "new_size": st.st_size,
                                    "old_mtime": old_mtime,
                                    "new_mtime": st.st_mtime,
                                }
                            ),
                        )
                    )

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


# singleton used by FastAPI startup/shutdown
case_file_watcher = CaseFileWatcher(interval_seconds=30)
