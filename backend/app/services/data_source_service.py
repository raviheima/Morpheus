from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from app.database import SessionLocal, Case, DataSource, ChainOfCustody
from app.hashing import calculate_hashes

IMAGE_EXTENSIONS = {".e01", ".ex01", ".s01", ".vhd", ".vhdx", ".dd", ".raw", ".img", ".001"}


def detect_image_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    mapping = {
        ".e01": "E01",
        ".ex01": "EX01",
        ".s01": "S01",
        ".vhd": "VHD",
        ".vhdx": "VHDX",
        ".dd": "raw",
        ".raw": "raw",
        ".img": "raw",
        ".001": "split_raw",
    }
    return mapping.get(ext, "unknown")


class DataSourceService:
    @staticmethod
    def is_forensic_image(file_path: str) -> bool:
        return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS

    @staticmethod
    def add_data_source(
        case_number: str,
        file_path: str,
        collected_by: str,
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> DataSource:
        path = Path(file_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Data source not found: {file_path}")

        if not DataSourceService.is_forensic_image(str(path)):
            raise ValueError(
                f"Not a forensic image extension: {path.suffix}. "
                "Use evidence artifacts for non-image files."
            )

        hash_info = calculate_hashes(str(path))

        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")

            ds = DataSource(
                case_id=case.id,
                label=label or path.name,
                original_filename=hash_info["filename"],
                stored_path=str(path),
                file_size=hash_info["size"],
                mime_type=hash_info.get("mime_type"),
                image_type=detect_image_type(path.name),
                sha256_hash=hash_info["sha256"],
                md5_hash=hash_info.get("md5"),
                collected_by=collected_by,
                notes=notes,
                is_consistent=True,
            )
            db.add(ds)
            db.flush()

            custody = ChainOfCustody(
                case_id=case.id,
                data_source_id=ds.id,
                action="data_source_added",
                actor=collected_by,
                details=json.dumps(
                    {
                        "filename": ds.original_filename,
                        "path": ds.stored_path,
                        "sha256": ds.sha256_hash,
                        "image_type": ds.image_type,
                        "size": ds.file_size,
                    }
                ),
            )
            db.add(custody)
            db.commit()
            db.refresh(ds)
            return ds
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def list_data_sources(case_number: str) -> List[DataSource]:
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")
            return (
                db.query(DataSource)
                .filter(DataSource.case_id == case.id)
                .order_by(DataSource.collected_at.desc())
                .all()
            )
        finally:
            db.close()

    @staticmethod
    def get_data_source(ds_id: int) -> Optional[DataSource]:
        db = SessionLocal()
        try:
            return db.query(DataSource).filter(DataSource.id == ds_id).first()
        finally:
            db.close()
