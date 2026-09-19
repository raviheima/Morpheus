from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app.database import SessionLocal, Case, DataSource, EvidenceItem, ChainOfCustody
from app.schemas import IntegrityCheckResponse, IntegrityItemResult


def _quick_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class IntegrityService:
    """
    Re-hash every registered data source + evidence file for a case
    and compare against the stored baseline.
    """

    @staticmethod
    def check_case(case_number: str, actor: str = "system") -> IntegrityCheckResponse:
        db = SessionLocal()
        try:
            case = db.query(Case).filter(Case.case_number == case_number).first()
            if not case:
                raise ValueError(f"Case not found: {case_number}")

            items: List[IntegrityItemResult] = []
            now = datetime.now(timezone.utc)

            # ---- data sources ----
            for ds in db.query(DataSource).filter(DataSource.case_id == case.id).all():
                result = IntegrityService._check_one(
                    kind="data_source",
                    record_id=ds.id,
                    filename=ds.original_filename,
                    stored_path=ds.stored_path,
                    expected_sha256=ds.sha256_hash,
                )
                items.append(result)

                ds.last_verified_at = now
                if result.status == "ok":
                    ds.is_consistent = True
                    ds.last_warning = None
                else:
                    ds.is_consistent = False
                    ds.last_warning = result.message

            # ---- evidence artifacts (only if they have a stored_path) ----
            for ev in db.query(EvidenceItem).filter(EvidenceItem.case_id == case.id).all():
                if not ev.stored_path:
                    items.append(
                        IntegrityItemResult(
                            kind="evidence",
                            id=ev.id,
                            filename=ev.original_filename,
                            stored_path=None,
                            status="ok",
                            message="No path stored (hash-only record)",
                            expected_sha256=ev.sha256_hash,
                        )
                    )
                    continue

                result = IntegrityService._check_one(
                    kind="evidence",
                    record_id=ev.id,
                    filename=ev.original_filename,
                    stored_path=ev.stored_path,
                    expected_sha256=ev.sha256_hash,
                )
                items.append(result)

                ev.last_verified_at = now
                if result.status == "ok":
                    ev.is_consistent = True
                    ev.last_warning = None
                else:
                    ev.is_consistent = False
                    ev.last_warning = result.message

            warnings = sum(1 for i in items if i.status != "ok")
            ok_count = sum(1 for i in items if i.status == "ok")

            # custody log
            custody = ChainOfCustody(
                case_id=case.id,
                action="integrity_check",
                actor=actor,
                details=json.dumps(
                    {
                        "total": len(items),
                        "ok": ok_count,
                        "warnings": warnings,
                        "items": [i.model_dump() for i in items],
                    },
                    default=str,
                ),
            )
            db.add(custody)
            db.commit()

            return IntegrityCheckResponse(
                case_number=case_number,
                checked_at=now,
                total=len(items),
                ok=ok_count,
                warnings=warnings,
                items=items,
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _check_one(
        kind: str,
        record_id: int,
        filename: str,
        stored_path: str,
        expected_sha256: str,
    ) -> IntegrityItemResult:
        path = Path(stored_path)

        if not path.exists():
            return IntegrityItemResult(
                kind=kind,
                id=record_id,
                filename=filename,
                stored_path=stored_path,
                status="missing",
                message=f"File missing at registered path: {stored_path}",
                expected_sha256=expected_sha256,
            )

        # resolve in case of symlink / relative drift
        resolved = str(path.resolve())
        if resolved != stored_path and path.name != Path(stored_path).name:
            # path string changed in a material way
            pass

        actual = _quick_sha256(path)
        if actual.lower() != expected_sha256.lower():
            return IntegrityItemResult(
                kind=kind,
                id=record_id,
                filename=filename,
                stored_path=stored_path,
                status="hash_mismatch",
                message=(
                    f"SHA-256 mismatch. Expected {expected_sha256[:16]}… "
                    f"got {actual[:16]}…. Data source may have been replaced or modified."
                ),
                expected_sha256=expected_sha256,
                actual_sha256=actual,
            )

        return IntegrityItemResult(
            kind=kind,
            id=record_id,
            filename=filename,
            stored_path=stored_path,
            status="ok",
            message="Integrity verified",
            expected_sha256=expected_sha256,
            actual_sha256=actual,
        )
