from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import cases, evidence

app = FastAPI(
    title="Morpheus API",
    description="Lightweight Unified Digital Forensics Tool",
    version="0.1.0-poc",
)

# Allow React frontend to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(cases.router)
app.include_router(evidence.router)


@app.get("/")
def root():
    return {
        "name": "Morpheus",
        "version": "0.1.0-poc",
        "status": "running"
    }
