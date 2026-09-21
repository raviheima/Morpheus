from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from app.database import SessionLocal, Case, DataSource, ChainOfCustody
from app.hashing import calculate_hashes

IMAGE_EXTENSIONS = {".e01", ".ex01", ".s01", ".vhd", ".vhdx", ".dd", ".raw", ".img", ".001"}


class DuplicateDataSourceError(ValueError):
    """Raised when a case already contains the same evidence fingerprint."""

    def __init__(self, existing: DataSource):
        self.existing_id = existing.id
        self.existing_path = existing.stored_path
        self.existing_filename = existing.original_filename
        self.sha256 = existing.sha256_hash
        super().__init__(
            "Duplicate data source: this file has the same SHA-256 as "
            f"data source #{existing.id} ({existing.original_filename}) at "
            f"{existing.stored_path}. Use PATCH /data-sources/by-id/{existing.id}/path "
            "if the evidence was moved, or register it in a different case."
        )


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

            duplicate = (
                db.query(DataSource)
                .filter(DataSource.case_id == case.id)
                .filter(DataSource.sha256_hash == hash_info["sha256"])
                .first()
            )
            if duplicate:
                raise DuplicateDataSourceError(duplicate)

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


    @staticmethod
    def update_path(
        ds_id: int,
        new_path: str,
        actor: str,
    ) -> DataSource:
        """
        Update stored_path when the file moved but content is unchanged.
        Rejects if file missing or SHA-256 does not match the registered fingerprint.
        """
        path = Path(new_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"File not found at new path: {new_path}")

        db = SessionLocal()
        try:
            ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
            if not ds:
                raise ValueError(f"Data source not found: {ds_id}")

            hash_info = calculate_hashes(str(path))
            actual = hash_info["sha256"]
            if actual.lower() != (ds.sha256_hash or "").lower():
                raise ValueError(
                    "SHA-256 mismatch: the file at the new path does not match the "
                    "fingerprint recorded at registration. Path was not updated. "
                    f"Expected {ds.sha256_hash[:16]}…, got {actual[:16]}…."
                )

            old_path = ds.stored_path
            ds.stored_path = str(path)
            ds.original_filename = hash_info.get("filename") or path.name
            ds.file_size = hash_info.get("size") or ds.file_size
            ds.is_consistent = True
            ds.last_warning = None
            ds.last_verified_at = None  # caller may re-verify

            custody = ChainOfCustody(
                case_id=ds.case_id,
                data_source_id=ds.id,
                action="path_updated",
                actor=actor,
                details=json.dumps(
                    {
                        "filename": ds.original_filename,
                        "old_path": old_path,
                        "new_path": str(path),
                        "sha256": ds.sha256_hash,
                        "note": "Location updated; fingerprint confirmed unchanged",
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
