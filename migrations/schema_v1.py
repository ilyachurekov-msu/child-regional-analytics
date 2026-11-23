from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Region(Base):
    __tablename__ = "regions"
    __table_args__ = {"schema": "core"}
    region_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    federal_district: Mapped[str] = mapped_column(Text)
    okato_code: Mapped[str | None] = mapped_column(Text)
    oktmo_code: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = {"schema": "core"}
    topic_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    parent_topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("core.topics.topic_id")
    )


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = {"schema": "core"}
    source_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    normalized_identifier: Mapped[str] = mapped_column(Text, unique=True)
    source_type: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class Indicator(Base):
    __tablename__ = "indicators"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('positive','negative','ambiguous')", name="direction"
        ),
        {"schema": "regional"},
    )
    indicator_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    topic_id: Mapped[str] = mapped_column(ForeignKey("core.topics.topic_id"))
    unit: Mapped[str] = mapped_column(Text)
    direction: Mapped[str] = mapped_column(Text)
    methodology: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Batch(Base):
    __tablename__ = "import_batches"
    __table_args__ = (
        UniqueConstraint("source_id", "checksum", "parser_version"),
        {"schema": "regional"},
    )
    batch_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(ForeignKey("core.sources.source_id"))
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checksum: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(Text, default="1.0.0")
    raw_path: Mapped[str] = mapped_column(Text)
    rows_processed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(Text, default="running")


class Value(Base):
    __tablename__ = "indicator_values"
    __table_args__ = (
        UniqueConstraint(
            "indicator_id", "region_id", "period_start", "period_end", "revision_number"
        ),
        CheckConstraint("period_end >= period_start", name="period"),
        CheckConstraint("revision_number > 0", name="revision"),
        CheckConstraint(
            "data_status IN ('official','missing','provisional')", name="status"
        ),
        CheckConstraint(
            "(value IS NULL AND data_status = 'missing') OR (value IS NOT NULL AND data_status != 'missing')",
            name="missing",
        ),
        Index(
            "uq_values_current",
            "indicator_id",
            "region_id",
            "period_start",
            "period_end",
            unique=True,
            postgresql_where=text("is_current"),
            sqlite_where=text("is_current = 1"),
        ),
        Index("ix_values_region_period", "region_id", "period_start"),
        {"schema": "regional"},
    )
    value_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    indicator_id: Mapped[UUID] = mapped_column(
        ForeignKey("regional.indicators.indicator_id")
    )
    region_id: Mapped[str] = mapped_column(ForeignKey("core.regions.region_id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    value: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    source_id: Mapped[UUID] = mapped_column(ForeignKey("core.sources.source_id"))
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("regional.import_batches.batch_id")
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_status: Mapped[str] = mapped_column(Text, default="official")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    revision_number: Mapped[int] = mapped_column(Integer, default=1)


class QualityIssue(Base):
    __tablename__ = "data_quality_issues"
    __table_args__ = {"schema": "regional"}
    issue_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("regional.import_batches.batch_id")
    )
    indicator_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("regional.indicators.indicator_id")
    )
    region_id: Mapped[str | None] = mapped_column(ForeignKey("core.regions.region_id"))
    issue_type: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    resolution_status: Mapped[str] = mapped_column(Text, default="open")


metadata = Base.metadata
