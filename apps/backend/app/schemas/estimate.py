from pydantic import BaseModel, field_validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime, date
import uuid


# ---- Line items ----

class LineItemCreate(BaseModel):
    zone_id: Optional[uuid.UUID] = None
    section: Optional[str] = None
    sort_order: int = 0
    name: str
    description: Optional[str] = None
    calc_type: str = "manual"
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    original_unit_price: Optional[Decimal] = None
    total_price: Decimal = Decimal("0")
    is_tbd: bool = False


class LineItemUpdate(BaseModel):
    zone_id: Optional[uuid.UUID] = None
    section: Optional[str] = None
    sort_order: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    calc_type: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit: Optional[str] = None
    unit_price: Optional[Decimal] = None
    total_price: Optional[Decimal] = None
    is_tbd: Optional[bool] = None


class LineItemOut(BaseModel):
    id: uuid.UUID
    estimate_id: uuid.UUID
    zone_id: Optional[uuid.UUID]
    section: Optional[str]
    sort_order: int
    name: str
    description: Optional[str]
    calc_type: str
    quantity: Optional[Decimal]
    unit: Optional[str]
    unit_price: Optional[Decimal]
    original_unit_price: Optional[Decimal] = None
    total_price: Decimal
    is_tbd: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


class ReorderRequest(BaseModel):
    ordered_ids: List[uuid.UUID]


# ---- Images ----

class ImageOut(BaseModel):
    id: uuid.UUID
    zone_id: Optional[uuid.UUID]
    slot: int
    file_path: str
    original_name: Optional[str]

    class Config:
        from_attributes = True


# ---- Zones ----

class ZoneCreate(BaseModel):
    zone_type: str = "wall"
    label: str = "Zone"
    sort_order: int = 0
    room_name: Optional[str] = None
    wall_name: Optional[str] = None
    wall_width_ft: Optional[Decimal] = None
    wall_height_ft: Optional[Decimal] = None
    square_footage: Optional[Decimal] = None
    linear_footage: Optional[Decimal] = None
    notes: Optional[str] = None


class ZoneUpdate(BaseModel):
    zone_type: Optional[str] = None
    label: Optional[str] = None
    sort_order: Optional[int] = None
    room_name: Optional[str] = None
    wall_name: Optional[str] = None
    wall_width_ft: Optional[Decimal] = None
    wall_height_ft: Optional[Decimal] = None
    square_footage: Optional[Decimal] = None
    linear_footage: Optional[Decimal] = None
    notes: Optional[str] = None


class ZoneOut(BaseModel):
    id: uuid.UUID
    estimate_id: uuid.UUID
    sort_order: int
    zone_type: str
    label: str
    room_name: Optional[str]
    wall_name: Optional[str]
    wall_width_ft: Optional[Decimal]
    wall_height_ft: Optional[Decimal]
    square_footage: Optional[Decimal]
    linear_footage: Optional[Decimal]
    notes: Optional[str]
    subtotal: Decimal
    line_items: List[LineItemOut] = []
    images: List[ImageOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Estimate ----

class EstimateCreate(BaseModel):
    type: str
    title: Optional[str] = None
    room_name: Optional[str] = None
    wall_name: Optional[str] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    prepared_by: Optional[str] = None
    estimate_date: Optional[date] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    wall_width_ft: Optional[Decimal] = None
    wall_height_ft: Optional[Decimal] = None
    square_footage: Optional[Decimal] = None


class EstimateUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    room_name: Optional[str] = None
    wall_name: Optional[str] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    prepared_by: Optional[str] = None
    estimate_date: Optional[date] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    wall_width_ft: Optional[Decimal] = None
    wall_height_ft: Optional[Decimal] = None
    square_footage: Optional[Decimal] = None
    subtotal: Optional[Decimal] = None
    final_total: Optional[Decimal] = None
    manual_override: Optional[bool] = None
    pdf_layout: Optional[dict] = None
    status: Optional[str] = None
    markup_pct: Optional[Decimal] = None
    discount_pct: Optional[Decimal] = None

    @field_validator('type')
    @classmethod
    def validate_type(cls, v):
        if v is not None and v not in ('pre', 'final', 'quick'):
            raise ValueError("type must be 'pre', 'final', or 'quick'")
        return v


class EstimateOut(BaseModel):
    source_estimate_id: Optional[uuid.UUID] = None
    cover_image_id: Optional[str] = None
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    status: str
    title: Optional[str]
    room_name: Optional[str]
    wall_name: Optional[str]
    client_name: Optional[str]
    project_name: Optional[str]
    prepared_by: Optional[str]
    estimate_date: Optional[date]
    description: Optional[str]
    notes: Optional[str]
    wall_width_ft: Optional[Decimal]
    wall_height_ft: Optional[Decimal]
    square_footage: Optional[Decimal]
    subtotal: Decimal
    final_total: Decimal
    manual_override: bool
    pdf_layout: Optional[dict]
    markup_pct: Optional[Decimal] = None
    discount_pct: Optional[Decimal] = None
    created_by_name: Optional[str] = None
    updated_by_name: Optional[str] = None
    zones: List[ZoneOut] = []
    line_items: List[LineItemOut] = []
    images: List[ImageOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EstimateListItem(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    title: Optional[str]
    room_name: Optional[str]
    client_name: Optional[str]
    final_total: Decimal
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True