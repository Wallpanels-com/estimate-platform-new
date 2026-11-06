"""Private employee directory; independent of platform login accounts."""
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class StaffMember(Base):
    __tablename__ = 'hr_staff'
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(64), unique=True)
    source: Mapped[dict] = mapped_column(JSON)
    name: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(240), default='')
    department: Mapped[str] = mapped_column(String(160), default='')
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
    links: Mapped[dict] = mapped_column(JSON, default=dict)
    manager_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('hr_staff.id'), nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(String(240), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
