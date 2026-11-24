from app.contract_version import CONTRACT_VERSION
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.schemas.api import RegionOut


class TopicContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic_id: str
    name: str
    parent_topic_id: str | None


class SourceContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: UUID
    source_type: str
    name: str
    url: str | None
    publisher: str | None
    created_at: datetime
    normalized_identifier: str


class PlatformContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_version: str = CONTRACT_VERSION
    regions: list[RegionOut]
    topics: list[TopicContract]
    sources: list[SourceContract]
