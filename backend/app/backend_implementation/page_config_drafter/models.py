"""SQLAlchemy ORM models for page config drafter."""

import enum
import uuid

from sqlalchemy import Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class LayoutType(enum.Enum):
    STANDARD = "STANDARD"
    HERO = "HERO"
    MINIMAL = "MINIMAL"


class VisibilityStatus(enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class VisualRepresentationType(enum.Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    CAROUSEL = "CAROUSEL"


class PageConfig(Base):
    __tablename__ = "page_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(255), nullable=False)
    page_title = Column(String(500), nullable=False)
    meta_description = Column(Text, nullable=False)
    layout_type = Column(
        SAEnum(
            LayoutType,
            values_callable=lambda x: [e.value for e in x],
            name="layout_type",
            create_type=False,
        ),
        nullable=False,
    )
    visibility_status = Column(
        SAEnum(
            VisibilityStatus,
            values_callable=lambda x: [e.value for e in x],
            name="visibility_status",
            create_type=False,
        ),
        nullable=False,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255), nullable=False)

    scroll_sections = relationship(
        "ScrollSection", back_populates="config", cascade="all, delete-orphan"
    )
    visual_representations = relationship(
        "VisualRepresentation", back_populates="config", cascade="all, delete-orphan"
    )
    sourcing_timeline_events = relationship(
        "SourcingTimelineEvent", back_populates="config", cascade="all, delete-orphan"
    )


class ScrollSection(Base):
    __tablename__ = "scroll_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id = Column(UUID(as_uuid=True), ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False)
    position = Column(Integer, nullable=False)
    heading = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    background_image_url = Column(String(2048), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    config = relationship("PageConfig", back_populates="scroll_sections")


class VisualRepresentation(Base):
    __tablename__ = "visual_representations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id = Column(UUID(as_uuid=True), ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False)
    type = Column(
        SAEnum(
            VisualRepresentationType,
            values_callable=lambda x: [e.value for e in x],
            name="visual_representation_type",
            create_type=False,
        ),
        nullable=False,
    )
    url = Column(String(2048), nullable=False)
    alt_text = Column(String(500), nullable=False, default="")
    position = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    config = relationship("PageConfig", back_populates="visual_representations")


class SourcingTimelineEvent(Base):
    __tablename__ = "sourcing_timeline_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    config_id = Column(UUID(as_uuid=True), ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    config = relationship("PageConfig", back_populates="sourcing_timeline_events")
