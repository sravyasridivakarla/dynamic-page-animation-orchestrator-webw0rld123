"""Pydantic schemas for page config drafter."""

import enum
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class WorkflowState(str, enum.Enum):
    DRAFT_PENDING = "DRAFT_PENDING"
    APPROVED = "APPROVED"
    PERSISTED = "PERSISTED"


class DraftOperation(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ScrollSectionDraft(BaseModel):
    id: Optional[UUID] = None
    position: int
    heading: str
    content: str
    background_image_url: Optional[str] = None


class VisualRepresentationDraft(BaseModel):
    id: Optional[UUID] = None
    type: str
    url: str
    alt_text: Optional[str] = None
    position: int


class SourcingTimelineEventDraft(BaseModel):
    id: Optional[UUID] = None
    timestamp: datetime
    event_type: str
    description: str


class PageConfigDraft(BaseModel):
    id: Optional[UUID] = None
    product_id: str
    page_title: str
    meta_description: str
    layout_type: str
    visibility_status: str
    scroll_sections: list[ScrollSectionDraft] = []
    visual_representations: list[VisualRepresentationDraft] = []
    sourcing_timeline_events: list[SourcingTimelineEventDraft] = []
    workflow_state: WorkflowState = WorkflowState.DRAFT_PENDING
    validation_warnings: list[str] = []


class DiffChange(BaseModel):
    before: Optional[str] = None
    after: Optional[str] = None


class KGSource(BaseModel):
    field: str
    source: str
    contribution: str


class DiffResponse(BaseModel):
    operation: DraftOperation
    draft: PageConfigDraft
    prior_state: Optional[PageConfigDraft] = None
    changes: dict[str, DiffChange] = {}
    kg_sources: list[KGSource] = []
    reasoning_trace: str = ""
    validation_warnings: list[str] = []
    approval_token: str


class CreateDraftRequest(BaseModel):
    product_id: str


class UpdateDraftRequest(BaseModel):
    product_id: str


class ApproveRequest(BaseModel):
    approval_token: str
    approved: bool


class ApproveResponse(BaseModel):
    id: UUID
    status: str

    model_config = {"from_attributes": True}


class RollbackRequest(BaseModel):
    to_version: UUID


class RollbackResponse(BaseModel):
    id: UUID
    status: str

    model_config = {"from_attributes": True}


class PageConfigResponse(BaseModel):
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
    scroll_sections: list[ScrollSectionDraft] = []
    visual_representations: list[VisualRepresentationDraft] = []
    sourcing_timeline_events: list[SourcingTimelineEventDraft] = []

    model_config = {"from_attributes": True}
