from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.database import Case, DataSource

DEMO_ORGANISATION = "hackathon-demo"


def get_authorized_case(
    db: Session,
    case_number: str | int,
    user: User,
    *,
    allow_deleted: bool = False,
) -> Case:
    case_filter = (
        Case.id == case_number if isinstance(case_number, int)
        else Case.case_number == case_number
    )
    case = db.query(Case).filter(case_filter).first()
    if not case or (not allow_deleted and case.status == "deleted"):
        raise HTTPException(status_code=404, detail="Case not found")
    if case.organisation != DEMO_ORGANISATION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to access this case",
        )
    return case


def get_authorized_data_source(db: Session, ds_id: int, user: User) -> DataSource:
    data_source = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    case = get_authorized_case(db, data_source.case_id, user)
    return data_source
