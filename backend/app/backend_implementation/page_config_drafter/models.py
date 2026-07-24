"""SQLAlchemy async models for Page Config Drafter."""

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class WorkflowState(str, enum.Enum):
    draft = "draft"
    pending = "pending"
    approved = "approved"


class ActionType(str, enum.Enum):
    draft_generated = "draft_generated"
    draft_approved = "draft_approved"
    draft_rejected = "draft_rejected"
    config_rolled_back = "config_rolled_back"
    deletion_proposed = "deletion_proposed"
    deletion_confirmed = "deletion_confirmed"


class PageConfig(Base):
    __tablename__ = "page_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(String(255), nullable=False, index=True)
    workflow_state = Column(
        Enum(WorkflowState, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=WorkflowState.draft.value,
    )
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    scroll_sections = relationship("ScrollSection", back_populates="page_config", cascade="all, delete-orphan")
    visual_representations = relationship("VisualRepresentation", back_populates="page_config", cascade="all, delete-orphan")
    sourcing_timeline_events = relationship("SourcingTimelineEvent", back_populates="page_config", cascade="all, delete-orphan")
    provenance_records = relationship("ProvenanceRecord", back_populates="page_config", cascade="all, delete-orphan")


class ScrollSection(Base):
    __tablename__ = "scroll_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_config_id = Column(UUID(as_uuid=True), ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    page_config = relationship("PageConfig", back_populates="scroll_sections")


class VisualRepresentation(Base):
    __tablename__ = "visual_representations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_config_id = Column(UUID(as_uuid=True), ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(100), nullable=False)
    url = Column(String(2048), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    page_config = relationship("PageConfig", back_populates="visual_representations")


class SourcingTimelineEvent(Base):
    __tablename__ = "sourcing_timeline_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_config_id = Column(UUID(as_uuid=True), ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(255), nullable=False)
    date = Column(DateTime(timezone=True), nullable=False)
    validated = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    page_config = relationship("PageConfig", back_populates="sourcing_timeline_events")


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_config_id = Column(UUID(as_uuid=True), ForeignKey("page_configs.id", ondelete="CASCADE"), nullable=False)
    action_type = Column(
        Enum(ActionType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    inputs = Column(JSON, nullable=True)
    sources = Column(JSON, nullable=True)
    reasoning_trace = Column(Text, nullable=True)
    diff_presented = Column(JSON, nullable=True)
    human_decision = Column(String(50), nullable=True)
    justification = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    page_config = relationship("PageConfig", back_populates="provenance_records")
