from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime

# Auth
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}

# LineItem
class LineItemCreate(BaseModel):
    name: str
    section: Optional[str] = None
    description: Optional[str] = None
    calc_type: str = "manual"  # sf|lf|fixed|manual
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: float = 0
    sort_order: int = 0

class LineItemUpdate(BaseModel):
    name: Optional[str] = None
    section: Optional[str] = None
    description: Optional[str] = None
    calc_type: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    sort_order: Optional[int] = None

class LineItemOut(LineItemCreate):
    id: UUID
    estimate_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}

class ReorderRequest(BaseModel):
    item_ids: List[UUID]  # ordered list

# Estimate
class EstimateCreate(BaseModel):
    type: str  # 'pre' | 'final'
    title: Optional[str] = None
    room_name: Optional[str] = None
    wall_name: Optional[str] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    prepared_by: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    wall_width_ft: Optional[float] = None
    wall_height_ft: Optional[float] = None
    square_footage: Optional[float] = None

class EstimateUpdate(BaseModel):
    title: Optional[str] = None
    room_name: Optional[str] = None
    wall_name: Optional[str] = None
    client_name: Optional[str] = None
    project_name: Optional[str] = None
    prepared_by: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    wall_width_ft: Optional[float] = None
    wall_height_ft: Optional[float] = None
    square_footage: Optional[float] = None
    subtotal: Optional[float] = None
    final_total: Optional[float] = None
    manual_override: Optional[bool] = None
    status: Optional[str] = None
    pdf_layout: Optional[dict] = None

class ImageOut(BaseModel):
    id: UUID
    slot: int
    file_path: str
    original_name: Optional[str]
    model_config = {"from_attributes": True}

class EstimateOut(EstimateCreate):
    id: UUID
    user_id: UUID
    status: str
    subtotal: float
    final_total: float
    manual_override: bool
    template: str
    line_items: List[LineItemOut] = []
    images: List[ImageOut] = []
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class EstimateListItem(BaseModel):
    id: UUID
    type: str
    title: Optional[str]
    room_name: Optional[str]
    client_name: Optional[str]
    status: str
    final_total: float
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# AI
class ExtractRequest(BaseModel):
    text: str
    estimate_id: Optional[UUID] = None

class ExtractedEstimate(BaseModel):
    title: Optional[str] = None
    room_name: Optional[str] = None
    wall_name: Optional[str] = None
    wall_width_ft: Optional[float] = None
    wall_height_ft: Optional[float] = None
    square_footage: Optional[float] = None
    description: Optional[str] = None
    line_items: List[LineItemCreate] = []
