from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, Base, engine, SessionLocal
from app.routers import cases, evidence, analysis, data_sources
from app.auth.router import router as auth_router
from app.auth.models import User
from app.auth.security import get_password_hash
from app.services.watcher_service import case_file_watcher

app = FastAPI(
    title="Morpheus API",
    description="Lightweight Unified Digital Forensics Tool",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def seed_default_users():
    defaults = [
        ("admin", "admin@morpheus.local", "admin123", "admin"),
        ("examiner", "examiner@morpheus.local", "exam123", "examiner"),
        ("viewer", "viewer@morpheus.local", "view123", "viewer"),
    ]
    db = SessionLocal()
    try:
        for username, email, password, role in defaults:
            if not db.query(User).filter(User.username == username).first():
                db.add(
                    User(
                        username=username,
                        email=email,
                        hashed_password=get_password_hash(password),
                        role=role,
                    )
                )
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    init_db()
    seed_default_users()
    case_file_watcher.start()


@app.on_event("shutdown")
def on_shutdown():
    case_file_watcher.stop()


app.include_router(auth_router)
app.include_router(cases.router)
app.include_router(evidence.router)
app.include_router(data_sources.router)
app.include_router(analysis.router)


@app.get("/")
def root():
    return {
        "name": "Morpheus",
        "version": "0.3.0",
        "status": "running",
        "roles": ["admin", "examiner", "viewer"],
    }
