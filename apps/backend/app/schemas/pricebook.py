import json
from pathlib import Path
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

CATEGORY_ICONS = json.loads((Path(__file__).resolve().parents[1] / "data/category_icons.json").read_text())

class BookModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class CategoryInput(BookModel):
    name: str = Field(min_length=1, max_length=160)
    name_ru: str = Field(default='', max_length=160)
    description: str = Field(default='', max_length=1200)
    description_ru: str = Field(default='', max_length=1200)
    icon: str = Field(default='folder', json_schema_extra={'enum': list(CATEGORY_ICONS)})

    @field_validator('icon')
    @classmethod
    def known_icon(cls, value):
        if value not in CATEGORY_ICONS:
            raise ValueError('Choose an icon from the library.')
        return value
    archived: bool = False
    expected_version: int | None = Field(default=None, ge=0)

class Specification(BookModel):
    name: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=300)

class ItemInput(BookModel):
    category_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    name_ru: str = Field(default='', max_length=200)
    description: str = Field(default='', max_length=2000)
    description_ru: str = Field(default='', max_length=2000)
    kind: Literal['work','material','service'] = 'work'
    unit: Literal['SF','LF','ea','HR','Fixed'] = 'ea'
    pricing_mode: Literal['unit','fixed','unpriced'] = 'unit'
    unit_price: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"), max_digits=12, decimal_places=2, allow_inf_nan=False)
    default_quantity: Decimal = Field(default=Decimal('1'), gt=0, le=999999, decimal_places=2, allow_inf_nan=False)
    parameters: list[Specification] = Field(default_factory=list, max_length=12)
    archived: bool = False
    expected_version: int | None = Field(default=None, ge=1)

    @field_validator('unit_price', 'default_quantity')
    @classmethod
    def two_decimals(cls, value):
        if value is not None and value != value.quantize(Decimal('.01')):
            raise ValueError('Use no more than two decimal places.')
        return value

    @model_validator(mode='after')
    def require_price(self):
        if self.pricing_mode != 'unpriced' and self.unit_price is None:
            raise ValueError('A price is required for a priced item.')
        if self.pricing_mode == 'unpriced': self.unit_price = None
        if self.pricing_mode == 'fixed': self.unit = 'Fixed'; self.default_quantity = Decimal('1')
        return self

class QuoteInput(BookModel):
    @field_validator('quantity')
    @classmethod
    def two_decimals(cls, value):
        if value != value.quantize(Decimal('.01')):
            raise ValueError('Use no more than two decimal places.')
        return value

    quantity: Decimal = Field(default=Decimal('1'), gt=0, le=999999, decimal_places=2, allow_inf_nan=False)
