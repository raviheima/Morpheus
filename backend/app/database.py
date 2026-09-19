from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Text,
    ForeignKey,
    BigInteger,
    Boolean,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime, timezone

DATABASE_URL = "sqlite:///morpheus.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(50), unique=True, nullable=False, index=True)
    case_name = Column(String(200), nullable=False)
    examiner_name = Column(String(100), nullable=False)
    examiner_email = Column(String(150), nullable=True)
    examiner_notes = Column(Text, nullable=True)
    organisation = Column(String(150), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(30), default="open")

    data_sources = relationship("DataSource", back_populates="case")
    evidence_items = relationship("EvidenceItem", back_populates="case")
    custody_logs = relationship("ChainOfCustody", back_populates="case")


class DataSource(Base):
    """
    Primary forensic image for a case (E01, VHD, raw, etc.).
    Path + hashes are the integrity baseline. If the file moves or
    its hash changes, the app must warn.
    """
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    label = Column(String(200), nullable=True)          # e.g. "Jimmy Wilson laptop"
    original_filename = Column(String(500), nullable=False)
    stored_path = Column(String(1000), nullable=False)  # absolute path on disk
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=True)
    image_type = Column(String(50), nullable=True)      # E01, VHD, raw, ...

    sha256_hash = Column(String(64), nullable=False, index=True)
    md5_hash = Column(String(32), nullable=True)

    collected_by = Column(String(100), nullable=False)
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)

    # integrity state
    is_consistent = Column(Boolean, default=True)
    last_verified_at = Column(DateTime, nullable=True)
    last_warning = Column(Text, nullable=True)

    case = relationship("Case", back_populates="data_sources")


class EvidenceItem(Base):
    """
    Non-image artifacts associated with a case
    (exported files, photos, notes, reports, etc.).
    """
    __tablename__ = "evidence_items"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)

    original_filename = Column(String(500), nullable=False)
    stored_path = Column(String(1000), nullable=True)   # optional path on disk
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=True)

    sha256_hash = Column(String(64), nullable=False, index=True)
    md5_hash = Column(String(32), nullable=True)

    collected_by = Column(String(100), nullable=False)
    collected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)

    is_consistent = Column(Boolean, default=True)
    last_verified_at = Column(DateTime, nullable=True)
    last_warning = Column(Text, nullable=True)

    case = relationship("Case", back_populates="evidence_items")


class ChainOfCustody(Base):
    __tablename__ = "chain_of_custody"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id"), nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    evidence_id = Column(Integer, ForeignKey("evidence_items.id"), nullable=True)

    action = Column(String(100), nullable=False)
    actor = Column(String(100), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    details = Column(Text, nullable=True)

    case = relationship("Case", back_populates="custody_logs")


def init_db():
    Base.metadata.create_all(bind=engine)
