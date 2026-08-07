"""Pydantic schemas for page config drafter request/response models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class WorkflowState(str, Enum):
    DRAFT_PENDING = "DRAFT_PENDING"
    APPROVED = "APPROVED"
    PERSISTED = "PERSISTED"


class DiffOperation(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ScrollSectionDraft(BaseModel):
    id: Optional[UUID] = None
    position: int
    heading: str
    content: str
    background_image_url: str = ""


class VisualRepresentationDraft(BaseModel):
    id: Optional[UUID] = None
    type: str
    url: str
    alt_text: str = ""
    position: int


class SourcingTimelineEventDraft(BaseModel):
    id: Optional[UUID] = None
    timestamp: datetime
    event_type: str
    description: str = ""


class PageConfigDraft(BaseModel):
    id: Optional[UUID] = None
    product_id: str
    page_title: str
    meta_description: str
    layout_type: str
    visibility_status: str
    scroll_sections: List[ScrollSectionDraft] = []
    visual_representations: List[VisualRepresentationDraft] = []
    sourcing_timeline_events: List[SourcingTimelineEventDraft] = []
    workflow_state: WorkflowState = WorkflowState.DRAFT_PENDING
    validation_warnings: List[str] = []


class DiffChange(BaseModel):
    before: Optional[Any] = None
    after: Optional[Any] = None


class KGSource(BaseModel):
    field: str
    source: str
    contribution: str


class DiffResponse(BaseModel):
    operation: DiffOperation
    draft: PageConfigDraft
    prior_state: Optional[PageConfigDraft] = None
    changes: Dict[str, DiffChange] = {}
    kg_sources: List[KGSource] = []
    reasoning_trace: str = ""
    validation_warnings: List[str] = []
    approval_token: str


class GenerateCreateDraftRequest(BaseModel):
    product_id: str


class GenerateUpdateDraftRequest(BaseModel):
    product_id: Optional[str] = None


class ApproveRequest(BaseModel):
    approval_token: str
    approved: bool


class ApproveResponse(BaseModel):
    id: UUID
    status: str


class RollbackRequest(BaseModel):
    to_version: UUID


class RollbackResponse(BaseModel):
    id: UUID
    status: str


class ScrollSectionResponse(BaseModel):
    id: UUID
    config_id: UUID
    position: int
    heading: str
    content: str
    background_image_url: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class VisualRepresentationResponse(BaseModel):
    id: UUID
    config_id: UUID
    type: str
    url: str
    alt_text: str
    position: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class SourcingTimelineEventResponse(BaseModel):
    id: UUID
    config_id: UUID
    timestamp: datetime
    event_type: str
    description: str
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class PageConfigDetailResponse(BaseModel):
    id: UUID
    product_id: str
    page_title: str
    meta_description: str
    layout_type: str
    visibility_status: str
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str
    scroll_sections: List[ScrollSectionResponse] = []
    visual_representations: List[VisualRepresentationResponse] = []
    sourcing_timeline_events: List[SourcingTimelineEventResponse] = []
    model_config = {"from_attributes": True}
