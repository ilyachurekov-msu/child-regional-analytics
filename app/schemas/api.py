from datetime import date, datetime
from decimal import Decimal
from typing import Generic, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    region_id: str
    name: str
    federal_district: str
    okato_code: str | None
    oktmo_code: str | None
    valid_from: date
    valid_to: date | None


class IndicatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    indicator_id: UUID
    code: str
    name: str
    description: str
    topic_id: str
    unit: str
    direction: str
    methodology: str
    is_active: bool


class ObservationOut(BaseModel):
    value_id: UUID
    indicator_code: str
    indicator_name: str
    region_id: str
    region_name: str
    federal_district: str
    period_start: date
    period_end: date
    value: Decimal | None
    unit: str
    source_id: UUID
    source_name: str
    source_url: str | None
    published_at: datetime | None
    loaded_at: datetime
    data_status: str
    revision_number: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list = Field(default_factory=list)


class ErrorOut(BaseModel):
    error: ErrorDetail
