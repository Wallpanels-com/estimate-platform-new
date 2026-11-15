"""Read-only GHL mirror. No foreign keys to, or mutations of, estimator records."""
from datetime import datetime
from sqlalchemy import String, DateTime, Boolean, Integer, Index, Text, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

JSON_PAYLOAD = JSONB().with_variant(JSON(), 'sqlite')


class SalesRecord(Base):
    __tablename__ = 'sales_records'
    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    external_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    contact_id: Mapped[str | None] = mapped_column(String(64))
    parent_id: Mapped[str | None] = mapped_column(String(128))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD)
    __table_args__ = (
        Index('ix_sales_kind_date', 'location_id', 'kind', 'occurred_at'),
        Index('ix_sales_contact', 'location_id', 'contact_id', 'kind'),
        Index('ix_sales_parent', 'location_id', 'kind', 'parent_id'),
    )


class SalesSync(Base):
    __tablename__ = 'sales_sync'
    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    resource: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[dict] = mapped_column(JSON_PAYLOAD, default=dict)
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class SalesJob(Base):
    __tablename__ = 'sales_jobs'
    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(180), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD, default=dict)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_run: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    error: Mapped[str | None] = mapped_column(Text)


class SalesAnalysis(Base):
    __tablename__ = 'sales_analyses'
    location_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(160), primary_key=True)
    contact_id: Mapped[str | None] = mapped_column(String(64), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON_PAYLOAD)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
