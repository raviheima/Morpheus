from __future__ import annotations

from typing import Any, Dict, List, Optional


# Artifact types discovered by FilesystemScanner
SCAN_ARTIFACT_TYPES = (
    "virtual_disks",
    "documents",
    "images",
    "registry_hives",
    "event_logs",
    "browser_artifacts",
    "prefetch",
    "lnk_files",
    "jump_lists",
    "recycle_bin",
    "executables",
    "databases",
    "archives",
    "encryption_related",
    "deleted_files",
    "suspicious_files",
    "other_interesting",
    "emails",
)


class ArtifactCollector:
    """
    Extracts a normalized list of forensic artifacts from an
    AnalysisOrchestrator report.

    - Does NOT modify the original report
    - Does NOT perform forensic analysis itself
    - Only provides a clean, consistent view of already-discovered items
    """

    def collect(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        artifacts: List[Dict[str, Any]] = []

        for volume in report.get("volume_scans", []):
            if not volume.get("scanned"):
                continue

            volume_name = volume.get("description") or "unknown"
            scan = volume.get("scan_result") or {}

            artifacts.extend(
                self._collect_filesystem_artifacts(scan, volume_name)
            )
            artifacts.extend(
                self._collect_browser_artifacts(
                    volume.get("browser_analysis") or {}, volume_name
                )
            )
            artifacts.extend(
                self._collect_email_artifacts(
                    volume.get("email_analysis") or {}, volume_name
                )
            )
            artifacts.extend(
                self._collect_text_artifacts(
                    volume.get("text_analysis") or {}, volume_name
                )
            )

        artifacts.extend(
            self._collect_nested_virtual_disks(
                report.get("nested_virtual_disks") or []
            )
        )

        return artifacts

    # ------------------------------------------------------------------ #
    # Private collectors
    # ------------------------------------------------------------------ #

    def _collect_filesystem_artifacts(
        self, scan: Dict[str, Any], volume_name: str
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for artifact_type in SCAN_ARTIFACT_TYPES:
            items = scan.get(artifact_type)
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                results.append(
                    self._build_artifact(
                        artifact_type=artifact_type,
                        source="filesystem_scanner",
                        item=item,
                        volume=volume_name,
                    )
                )
        return results

    def _collect_browser_artifacts(
        self, browser_result: Dict[str, Any], volume_name: str
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for browser_type in ("chrome_edge", "firefox", "internet_explorer"):
            entries = browser_result.get(browser_type) or []
            if not isinstance(entries, list):
                continue

            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                results.append(
                    self._build_artifact(
                        artifact_type="browser_history",
                        source="browser_analyzer",
                        item=entry,
                        volume=volume_name,
                        extra_metadata={"browser": browser_type},
                    )
                )
        return results

    def _collect_email_artifacts(
        self, email_result: Dict[str, Any], volume_name: str
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for email in email_result.get("parsed_emails") or []:
            if not isinstance(email, dict):
                continue
            results.append(
                self._build_artifact(
                    artifact_type="parsed_email",
                    source="email_analyzer",
                    item=email,
                    volume=volume_name,
                    path_key="source_path",
                )
            )
        return results

    def _collect_text_artifacts(
        self, text_result: Dict[str, Any], volume_name: str
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for doc in text_result.get("documents_of_interest") or []:
            if not isinstance(doc, dict):
                continue
            results.append(
                self._build_artifact(
                    artifact_type="document_of_interest",
                    source="text_file_analyzer",
                    item=doc,
                    volume=volume_name,
                )
            )

        for enc in text_result.get("encrypted_messages") or []:
            if not isinstance(enc, dict):
                continue
            results.append(
                self._build_artifact(
                    artifact_type="encrypted_message",
                    source="text_file_analyzer",
                    item=enc,
                    volume=volume_name,
                )
            )
        return results

    def _collect_nested_virtual_disks(
        self, nested: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for vhd in nested:
            if not isinstance(vhd, dict):
                continue

            vhd_path = vhd.get("vhd_path") or vhd.get("path")
            results.append(
                self._build_artifact(
                    artifact_type="virtual_disk",
                    source="virtual_disk_handler",
                    item={
                        "path": vhd_path,
                        "name": self._filename_from_path(vhd_path),
                        "size": vhd.get("size"),
                        "created": vhd.get("created"),
                        "modified": vhd.get("modified"),
                        "accessed": vhd.get("accessed"),
                        "deleted": False,
                    },
                    volume="nested",
                )
            )

            for scan in vhd.get("scans") or []:
                if not isinstance(scan, dict):
                    continue
                results.extend(
                    self._collect_filesystem_artifacts(scan, f"nested:{vhd_path}")
                )
        return results

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_artifact(
        self,
        artifact_type: str,
        source: str,
        item: Dict[str, Any],
        volume: str,
        path_key: str = "path",
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        path = item.get(path_key) or item.get("path")
        name = item.get("name") or self._filename_from_path(path)

        artifact: Dict[str, Any] = {
            "artifact_type": artifact_type,
            "source": source,
            "path": path,
            "name": name,
            "size": item.get("size"),
            "created": item.get("created"),
            "modified": item.get("modified"),
            "accessed": item.get("accessed"),
            "deleted": bool(item.get("deleted", False)),
            "volume": volume,
            "metadata": dict(item),  # preserve everything
        }

        if extra_metadata:
            artifact["metadata"].update(extra_metadata)

        return artifact

    @staticmethod
    def _filename_from_path(path: Optional[str]) -> Optional[str]:
        if not path:
            return None
        normalized = path.replace("\\", "/").rstrip("/")
        return normalized.rsplit("/", 1)[-1] if normalized else None
