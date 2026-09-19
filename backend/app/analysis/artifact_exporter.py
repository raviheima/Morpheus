from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ArtifactExporter:
    """
    Exports normalized forensic artifacts as real files + a JSON manifest.

    The exporter is deliberately unaware of the underlying evidence source
    (E01 / VHD / raw / mounted FS).  The caller supplies a `read_artifact`
    callback that returns the raw bytes for a given artifact dict.
    """

    def export(
        self,
        artifacts: List[Dict[str, Any]],
        output_dir: str | Path,
        read_artifact: Callable[[Dict[str, Any]], bytes],
    ) -> Dict[str, Any]:
        output_path = Path(output_dir)
        files_dir = output_path / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        exported_artifacts: List[Dict[str, Any]] = []

        for index, artifact in enumerate(artifacts):
            entry = dict(artifact)  # shallow copy
            try:
                data = read_artifact(artifact)
                if not isinstance(data, bytes):
                    raise TypeError("read_artifact must return bytes")

                filename = self._safe_filename(
                    artifact.get("name") or f"artifact_{index}"
                )
                # avoid collisions
                target = files_dir / f"{index:05d}_{filename}"
                target.write_bytes(data)

                entry["exported"] = True
                entry["exported_path"] = str(target)
                entry["exported_size"] = len(data)
                entry["sha256"] = hashlib.sha256(data).hexdigest()
                entry["export_status"] = "ok"
            except Exception as exc:
                entry["exported"] = False
                entry["export_status"] = "failed"
                entry["export_error"] = str(exc)

            exported_artifacts.append(entry)

        manifest = {
            "artifact_count": len(artifacts),
            "exported_count": sum(1 for a in exported_artifacts if a.get("exported")),
            "failed_count": sum(1 for a in exported_artifacts if not a.get("exported")),
            "artifacts": exported_artifacts,
        }

        manifest_path = output_path / "artifacts.json"
        with manifest_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False, default=str)

        return manifest

    def export_json(
        self,
        artifacts: List[Dict[str, Any]],
        output_path: str | Path,
    ) -> Path:
        """Write only the JSON manifest (no file extraction)."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "artifact_count": len(artifacts),
            "artifacts": artifacts,
        }
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)

        return path

    @staticmethod
    def _safe_filename(name: str) -> str:
        # keep only safe characters
        safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
        return safe.strip() or "unnamed"
