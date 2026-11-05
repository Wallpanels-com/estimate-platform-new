"""HR records are independent of estimates and their pricing data."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Integer, Boolean, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Vacancy(Base):
    __tablename__ = 'hr_vacancies'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String, default='')
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Candidate(Base):
    __tablename__ = 'hr_candidates'
    __table_args__ = (UniqueConstraint('vacancy_id', 'fingerprint', name='uq_hr_candidate_source'),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('hr_vacancies.id'), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(240))
    email: Mapped[str] = mapped_column(String(320), default='')
    telegram_username: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone: Mapped[str] = mapped_column(String(100), default='')
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(240), default='')
    status: Mapped[str] = mapped_column(String(30), default='new', index=True)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default='false', nullable=False)
    priority: Mapped[bool] = mapped_column(Boolean, default=False)
    location: Mapped[str] = mapped_column(String(240), default='')
    location_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(String, default='')
    updated_by: Mapped[str] = mapped_column(String(240), default='')
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ImportBatch(Base):
    __tablename__ = 'hr_imports'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('hr_vacancies.id'), index=True)
    filename: Mapped[str] = mapped_column(String(240))
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateAIReview(Base):
    __tablename__ = 'hr_ai_reviews'
    candidate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('hr_candidates.id'), primary_key=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
    message_draft: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
