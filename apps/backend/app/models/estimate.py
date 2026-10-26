import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from sqlalchemy import String, DateTime, Numeric, Boolean, Integer, Text, ForeignKey, JSON, func, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Estimate(Base):
    __tablename__ = "estimates"

    @property
    def revision(self) -> str:
        import hashlib
        state = f"{self.id}|{self.updated_at}|{getattr(self, '_source_revision', None)}"
        return hashlib.sha256(state.encode()).hexdigest()

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_name: Mapped[Optional[str]] = mapped_column(String)
    updated_by_name: Mapped[Optional[str]] = mapped_column(String)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'pre' | 'final'
    source_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("estimates.id", ondelete="CASCADE"), nullable=True, unique=True)
    branch_state: Mapped[Optional[dict]] = mapped_column(JSON)
    cover_image_id: Mapped[Optional[str]] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="draft")
    title: Mapped[Optional[str]] = mapped_column(String)
    room_name: Mapped[Optional[str]] = mapped_column(String)
    wall_name: Mapped[Optional[str]] = mapped_column(String)
    client_name: Mapped[Optional[str]] = mapped_column(String)
    project_name: Mapped[Optional[str]] = mapped_column(String)
    prepared_by: Mapped[Optional[str]] = mapped_column(String)
    estimate_date: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    wall_width_ft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    wall_height_ft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    square_footage: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    final_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    markup_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    discount_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    pdf_layout: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    zones: Mapped[list["EstimateZone"]] = relationship("EstimateZone", back_populates="estimate", cascade="all, delete-orphan", order_by="EstimateZone.sort_order")
    line_items: Mapped[list["LineItem"]] = relationship("LineItem", back_populates="estimate", cascade="all, delete-orphan", order_by="LineItem.sort_order")
    images: Mapped[list["EstimateImage"]] = relationship("EstimateImage", back_populates="estimate", cascade="all, delete-orphan")
    voice_files: Mapped[list["VoiceFile"]] = relationship("VoiceFile", back_populates="estimate", cascade="all, delete-orphan")
    pdf_files: Mapped[list["PdfFile"]] = relationship("PdfFile", back_populates="estimate", cascade="all, delete-orphan")


class EstimateZone(Base):
    """A single zone/wall/room within an estimate. Each zone becomes its own PDF page."""
    __tablename__ = "estimate_zones"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    estimate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    zone_type: Mapped[str] = mapped_column(String, default="wall")  # wall | cabinet | mirror
    label: Mapped[str] = mapped_column(String, default="Zone")
    room_name: Mapped[Optional[str]] = mapped_column(String)
    wall_name: Mapped[Optional[str]] = mapped_column(String)
    wall_width_ft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    wall_height_ft: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    square_footage: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    linear_footage: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    estimate: Mapped["Estimate"] = relationship("Estimate", back_populates="zones")
    line_items: Mapped[list["LineItem"]] = relationship("LineItem", back_populates="zone", cascade="all, delete-orphan", order_by="LineItem.sort_order")
    images: Mapped[list["EstimateImage"]] = relationship("EstimateImage", back_populates="zone", cascade="all, delete-orphan")

    @property
    def subtotal(self) -> Decimal:
        return sum((item.total_price for item in self.line_items), Decimal("0"))


class LineItem(Base):
    __tablename__ = "line_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    estimate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False, index=True)
    zone_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("estimate_zones.id", ondelete="CASCADE"), nullable=True, index=True)
    section: Mapped[Optional[str]] = mapped_column(String)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    calc_type: Mapped[str] = mapped_column(String, default="manual")  # sf|lf|fixed|manual
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    unit: Mapped[Optional[str]] = mapped_column(String)
    unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    original_unit_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_tbd: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    estimate: Mapped["Estimate"] = relationship("Estimate", back_populates="line_items")
    zone: Mapped[Optional["EstimateZone"]] = relationship("EstimateZone", back_populates="line_items")


class EstimateImage(Base):
    __tablename__ = "estimate_images"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    estimate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False)
    zone_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("estimate_zones.id", ondelete="CASCADE"), nullable=True, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..4
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    estimate: Mapped["Estimate"] = relationship("Estimate", back_populates="images")
    zone: Mapped[Optional["EstimateZone"]] = relationship("EstimateZone", back_populates="images")


class VoiceFile(Base):
    __tablename__ = "voice_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    estimate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    transcript: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    estimate: Mapped["Estimate"] = relationship("Estimate", back_populates="voice_files")


class PdfFile(Base):
    __tablename__ = "pdf_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    estimate_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("estimates.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    estimate: Mapped["Estimate"] = relationship("Estimate", back_populates="pdf_files")


class PricingConfig(Base):
    """Singleton-style table: holds the active pricing configuration as JSON.
    If no row exists, the app falls back to hardcoded defaults (see
    app/services/pricing_config.py: DEFAULT_PRICING_CONFIG)."""
    __tablename__ = "pricing_config"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_by_name: Mapped[Optional[str]] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())