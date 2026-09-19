from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


class TimelineBuilder:
    """
    Builds a unified forensic timeline using Plaso (log2timeline + psort).

    This class is a thin adapter around the Plaso CLI tools so that the rest
    of the application stays decoupled from Plaso internals.
    """

    def __init__(
        self,
        log2timeline_bin: str = "log2timeline.py",
        psort_bin: str = "psort.py",
    ):
        self.log2timeline = log2timeline_bin
        self.psort = psort_bin

    def build_from_image(
        self,
        image_path: str | Path,
        output_dir: str | Path,
        parsers: Optional[List[str]] = None,
        timezone: str = "UTC",
    ) -> Dict[str, Any]:
        """
        Run Plaso against a forensic image and produce a JSON-L timeline.
        """
        image_path = Path(image_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        storage = output_dir / "plaso.storage"
        timeline_jsonl = output_dir / "timeline.jsonl"

        # 1. log2timeline
        cmd = [
            self.log2timeline,
            "--storage-file", str(storage),
            "--status-view", "none",
            str(image_path),
        ]
        if parsers:
            cmd.extend(["--parsers", ",".join(parsers)])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"log2timeline failed:\n{result.stderr or result.stdout}"
            )

        # 2. psort → JSON-L
        psort_cmd = [
            self.psort,
            "--output-format", "json_line",
            "--output-file", str(timeline_jsonl),
            str(storage),
        ]
        result = subprocess.run(
            psort_cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"psort failed:\n{result.stderr or result.stdout}"
            )

        # 3. Load a lightweight summary
        events = []
        with timeline_jsonl.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        return {
            "storage_file": str(storage),
            "timeline_file": str(timeline_jsonl),
            "event_count": len(events),
            "events_sample": events[:50],  # first 50 for preview
        }

    def build_from_artifacts(
        self,
        artifacts: List[Dict[str, Any]],
        output_path: str | Path,
    ) -> Path:
        """
        Lightweight timeline built only from timestamps already present
        in the normalized artifacts (no Plaso needed).
        Useful as a fast preview.
        """
        entries = []
        for art in artifacts:
            for ts_field in ("created", "modified", "accessed"):
                ts = art.get(ts_field)
                if not ts:
                    continue
                entries.append(
                    {
                        "timestamp": ts,
                        "timestamp_desc": ts_field,
                        "source": art.get("source"),
                        "artifact_type": art.get("artifact_type"),
                        "path": art.get("path"),
                        "name": art.get("name"),
                        "volume": art.get("volume"),
                        "deleted": art.get("deleted"),
                    }
                )

        entries.sort(key=lambda e: e["timestamp"] or "")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e, default=str) + "\n")

        return path
