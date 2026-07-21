"""Pydantic request/response schemas for Page Config Drafter."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from .models import WorkflowState


# --- child schemas ---

class ScrollSectionResponse(BaseModel):
    id: UUID
    page_config_id: UUID
    order: int
    content: str
    created_at: datetime
    model_config = {"from_attributes": True}


class VisualRepresentationResponse(BaseModel):
    id: UUID
    page_config_id: UUID
    type: str
    url: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SourcingTimelineEventResponse(BaseModel):
    id: UUID
    page_config_id: UUID
    event_type: str
    date: datetime
    validated: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class ProvenanceRecordResponse(BaseModel):
    id: UUID
    page_config_id: UUID
    action_type: str
    inputs: Dict[str, Any]
    sources: Dict[str, Any]
    reasoning_trace: str
    diff_presented: Dict[str, Any]
    human_decision: Optional[str] = None
    justification: Optional[str] = None
    timestamp: datetime
    model_config = {"from_attributes": True}


class PageConfigResponse(BaseModel):
    id: UUID
    product_id: str
    workflow_state: WorkflowState
    version: int
    created_at: datetime
    updated_at: datetime
    scroll_sections: List[ScrollSectionResponse] = []
    visual_representations: List[VisualRepresentationResponse] = []
    sourcing_timeline_events: List[SourcingTimelineEventResponse] = []
    model_config = {"from_attributes": True}


# --- request schemas ---

class ScrollSectionInput(BaseModel):
    order: int
    content: str


class VisualRepresentationInput(BaseModel):
    type: str
    url: str


class SourcingTimelineEventInput(BaseModel):
    event_type: str
    date: datetime


class DraftRequest(BaseModel):
    product_id: str = Field(..., min_length=1)
    scroll_sections: List[ScrollSectionInput] = Field(default_factory=list)
    visual_representations: List[VisualRepresentationInput] = Field(default_factory=list)
    sourcing_timeline_events: List[SourcingTimelineEventInput] = Field(default_factory=list)
    justification: Optional[str] = None


class ApproveRequest(BaseModel):
    justification: Optional[str] = None


class RejectRequest(BaseModel):
    justification: Optional[str] = None


# --- diff/response schemas ---

class CompletenessWarning(BaseModel):
    field: str
    message: str


class EventTypeWarning(BaseModel):
    event_type: str
    message: str


class DiffResponse(BaseModel):
    draft_id: UUID
    product_id: str
    workflow_state: WorkflowState
    scroll_sections: List[ScrollSectionResponse]
    visual_representations: List[VisualRepresentationResponse]
    sourcing_timeline_events: List[SourcingTimelineEventResponse]
    completeness_warnings: List[CompletenessWarning] = []
    event_type_warnings: List[EventTypeWarning] = []
    unwind_option: bool = False
    model_config = {"from_attributes": True}


class RollbackResponse(BaseModel):
    config_id: UUID
    restored_version: int
    message: str


class DeleteProposalResponse(BaseModel):
    config_id: UUID
    workflow_state: WorkflowState
    diff: DiffResponse
    unwind_option: bool = True
    message: str


class DeleteConfirmResponse(BaseModel):
    config_id: UUID
    message: str
