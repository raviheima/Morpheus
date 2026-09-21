from __future__ import annotations

import json
from typing import Any, Optional

from app.database import AuditLog, Case, ChainOfCustody, SessionLocal


def log_general_action(
    action: str,
    actor: str,
    details: Optional[dict[str, Any]] = None,
    case_id: Optional[int] = None,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AuditLog(
                case_id=case_id,
                action=action,
                actor=actor,
                details=json.dumps(details or {}, default=str),
            )
        )
        db.commit()
    finally:
        db.close()


def log_case_action(
    case_number: str,
    action: str,
    actor: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.case_number == case_number).first()
        if not case:
            return
        db.add(
            ChainOfCustody(
                case_id=case.id,
                action=action,
                actor=actor,
                details=json.dumps(details or {}, default=str),
            )
        )
        db.commit()
    finally:
        db.close()
