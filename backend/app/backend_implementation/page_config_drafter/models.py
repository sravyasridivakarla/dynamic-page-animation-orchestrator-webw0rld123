"""SQLAlchemy ORM models for page config drafter."""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class LayoutType(str, enum.Enum):
    STANDARD = "STANDARD"
    HERO = "HERO"
    MINIMAL = "MINIMAL"


class VisibilityStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class VisualRepresentationType(str, enum.Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    CAROUSEL = "CAROUSEL"


class PageConfig(Base):
    __tablename__ = "page_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    page_title: Mapped[str] = mapped_column(String(500), nullable=False)
    meta_description: Mapped[str] = mapped_column(Text, nullable=False)
    layout_type: Mapped[str] = mapped_column(
        SAEnum(LayoutType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    visibility_status: Mapped[str] = mapped_column(
        SAEnum(VisibilityStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(255), nullable=False)

    scroll_sections: Mapped[list["ScrollSection"]] = relationship(
        "ScrollSection", back_populates="config", cascade="all, delete-orphan"
    )
    visual_representations: Mapped[list["VisualRepresentation"]] = relationship(
        "VisualRepresentation", back_populates="config", cascade="all, delete-orphan"
    )
    sourcing_timeline_events: Mapped[list["SourcingTimelineEvent"]] = relationship(
        "SourcingTimelineEvent", back_populates="config", cascade="all, delete-orphan"
    )


class ScrollSection(Base):
    __tablename__ = "scroll_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("page_configs.id"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    background_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    config: Mapped["PageConfig"] = relationship(
        "PageConfig", back_populates="scroll_sections"
    )


class VisualRepresentation(Base):
    __tablename__ = "visual_representations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("page_configs.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(
        SAEnum(
            VisualRepresentationType,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    config: Mapped["PageConfig"] = relationship(
        "PageConfig", back_populates="visual_representations"
    )


class SourcingTimelineEvent(Base):
    __tablename__ = "sourcing_timeline_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("page_configs.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    config: Mapped["PageConfig"] = relationship(
        "PageConfig", back_populates="sourcing_timeline_events"
    )
