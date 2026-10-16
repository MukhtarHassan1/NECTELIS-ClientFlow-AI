from __future__ import annotations
import os
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, ForeignKey, UniqueConstraint, String, DateTime, Integer, Boolean, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid(prefix: str) -> str:
    return f'{prefix}_{uuid4().hex[:16]}'

class Base(DeclarativeBase):
    pass

class Contact(Base):
    __tablename__ = 'contacts'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    client_key: Mapped[str] = mapped_column(String(80), index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    service: Mapped[str | None] = mapped_column(String(150), nullable=True)
    stage: Mapped[str] = mapped_column(String(90))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (
        UniqueConstraint('client_key', 'email', name='uq_contact_email'),
        UniqueConstraint('client_key', 'phone', name='uq_contact_phone'),
    )

class Event(Base):
    __tablename__ = 'events'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    client_key: Mapped[str] = mapped_column(String(80))
    source: Mapped[str] = mapped_column(String(80))
    external_event_id: Mapped[str] = mapped_column(String(120))
    request_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default='processing')
    contact_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    appointment_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('client_key', 'source', 'external_event_id', name='uq_event_identity'),)

class Booking(Base):
    __tablename__ = 'bookings'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    client_key: Mapped[str] = mapped_column(String(80))
    contact_id: Mapped[str] = mapped_column(String(50), ForeignKey('contacts.id'))
    event_id: Mapped[str] = mapped_column(String(50), ForeignKey('events.id'), unique=True)
    start_at: Mapped[str] = mapped_column(String(50))  # normalized UTC instant
    duration_minutes: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint('client_key', 'start_at', name='uq_booking_slot'),)

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(50), ForeignKey('events.id'), index=True)
    step: Mapped[str] = mapped_column(String(70))
    outcome: Mapped[str] = mapped_column(String(30))
    detail: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Rejection(Base):
    __tablename__ = 'rejections'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(120), default='unknown')
    reason: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Notification(Base):
    __tablename__ = 'notifications'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(50), ForeignKey('events.id'), index=True)
    audience: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class FollowUp(Base):
    __tablename__ = 'followups'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(50), ForeignKey('events.id'))
    type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default='queued_for_human_review')
    reason: Mapped[str] = mapped_column(String(160))


class ProviderJob(Base):
    """Durable live connector boundary. Interrupted jobs require reconciliation."""
    __tablename__='provider_jobs'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    provider: Mapped[str] = mapped_column(String(25))
    external_event_key: Mapped[str] = mapped_column(String(120))
    fingerprint: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default='started')
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__=(UniqueConstraint('provider','external_event_key',name='uq_provider_job'),)

class Delivery(Base):
    """Twilio outbound lifecycle without retaining recipient or message content."""
    __tablename__ = 'deliveries'
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(120), unique=True)
    message_sid: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(24))
    channel: Mapped[str] = mapped_column(String(30), default='twilio')
    error_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

engine = None
SessionLocal = None

def connect_db(url: str | None = None):
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    url = url or os.getenv('DATABASE_URL', 'sqlite:///./clientflow_demo.sqlite3')
    extra = {'connect_args': {'check_same_thread': False, 'timeout': 20}} if url.startswith('sqlite:') else {}
    engine = create_engine(url, pool_pre_ping=True, **extra)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(engine)
    # Forward-compatible upgrade for a local SQLite database created by the initial proof.
    # Keep the existing synthetic records rather than silently wiping user test history.
    if url.startswith('sqlite:'):
        from sqlalchemy import text
        with engine.begin() as conn:
            columns = {row[1] for row in conn.execute(text('PRAGMA table_info(events)'))}
            if 'request_fingerprint' not in columns:
                conn.execute(text('ALTER TABLE events ADD COLUMN request_fingerprint VARCHAR(64)'))
    return SessionLocal

def session():
    if SessionLocal is None:
        connect_db()
    return SessionLocal()

def audit(db, event_id, step, outcome, detail='', attempts=1):
    entry = Audit(id=uid('aud'), event_id=event_id, step=step, outcome=outcome,
                  detail=detail[:500], attempts=attempts)
    db.add(entry)
    db.flush()
    return entry.id
