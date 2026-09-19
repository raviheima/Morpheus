#!/usr/bin/env python3
"""
export_artifacts.py

Run after (or instead of) test_orchestrator.py.
Extracts real file content for the most interesting artifacts.
"""

from pathlib import Path
import pytsk3
import pyewf

from app.analysis.orchestrator import AnalysisOrchestrator
from app.analysis.artifacts import ArtifactCollector
from app.analysis.artifact_exporter import ArtifactExporter
from app.analysis.identifier import EWFImgInfo


# ── same image you used in test_orchestrator.py ─────────────────────────
EVIDENCE = "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01"
OUTPUT   = "./exported_artifacts"          # change if you want


def open_image(path: str):
    path = Path(path)
    if path.name.lower().endswith((".e01", ".ex01", ".s01")):
        filenames = pyewf.glob(str(path))
        handle = pyewf.handle()
        handle.open(filenames)
        return EWFImgInfo(handle)
    return pytsk3.Img_Info(str(path))


def make_reader(img_info, volume_offset: int):
    """Callback that the exporter calls for every artifact."""
    fs = pytsk3.FS_Info(img_info, offset=volume_offset)

    def read_artifact(artifact: dict) -> bytes:
        path = artifact.get("path") or ""
        # clean Windows-style path for pytsk3
        tsk_path = path.replace("\\", "/")
        if ":" in tsk_path:                         # strip C:
            tsk_path = tsk_path.split(":", 1)[-1]
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        file_obj = fs.open(path=tsk_path)
        size = file_obj.info.meta.size or 0
        # 50 MB safety limit – raise if needed
        return file_obj.read_random(0, min(size, 50 * 1024 * 1024))

    return read_artifact


def main():
    print("[+] Running orchestrator …")
    report = AnalysisOrchestrator().analyze(EVIDENCE)

    print("[+] Collecting normalized artifacts …")
    artifacts = ArtifactCollector().collect(report)
    print(f"    → {len(artifacts)} artifacts total")

    # only export the high-value ones (optional filter)
    interesting_types = {
        "document_of_interest",
        "encrypted_message",
        "parsed_email",
        "deleted_files",
        "documents",
        "suspicious_files",
        "registry_hives",
    }
    to_export = [
        a for a in artifacts
        if a["artifact_type"] in interesting_types
    ]
    print(f"    → exporting {len(to_export)} high-value artifacts")

    # volume offset from the first scanned volume
    vol = next(v for v in report["volume_scans"] if v.get("scanned"))
    offset = vol["start_sector"] * 512

    img_info = open_image(EVIDENCE)
    reader = make_reader(img_info, offset)

    print(f"[+] Writing files to {OUTPUT}/ …")
    manifest = ArtifactExporter().export(to_export, OUTPUT, reader)

    print(f"\nDone.")
    print(f"  Exported : {manifest['exported_count']}")
    print(f"  Failed   : {manifest['failed_count']}")
    print(f"  Manifest : {OUTPUT}/artifacts.json")
    print(f"  Files    : {OUTPUT}/files/")


if __name__ == "__main__":
    main()
