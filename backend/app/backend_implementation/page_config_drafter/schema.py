"""Pydantic v2 schemas for Page Config Drafter."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────────────────────────────

class DraftGenerateRequest(BaseModel):
    product_id: str = Field(..., min_length=1)


class ApproveRequest(BaseModel):
    justification: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class RollbackRequest(BaseModel):
    version: int = Field(..., ge=1)


class DeleteConfirmRequest(BaseModel):
    explicit_confirm: bool


# ── Child record schemas ───────────────────────────────────────────────────────

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
    inputs: Optional[Dict[str, Any]] = None
    sources: Optional[Dict[str, Any]] = None
    reasoning_trace: Optional[str] = None
    diff_presented: Optional[Dict[str, Any]] = None
    human_decision: Optional[str] = None
    justification: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


# ── Parent config schemas ──────────────────────────────────────────────────────

class PageConfigResponse(BaseModel):
    id: UUID
    product_id: str
    workflow_state: str
    version: int
    created_at: datetime
    updated_at: datetime
    scroll_sections: List[ScrollSectionResponse] = []
    visual_representations: List[VisualRepresentationResponse] = []
    sourcing_timeline_events: List[SourcingTimelineEventResponse] = []

    model_config = {"from_attributes": True}


# ── Diff schemas ───────────────────────────────────────────────────────────────

class DraftDiffResponse(BaseModel):
    draft_id: UUID
    product_id: str
    diff: Dict[str, Any]
    completeness_warnings: List[str] = []
    has_incomplete_fields: bool = False
    event_type_warnings: List[str] = []


class DeleteProposalResponse(BaseModel):
    config_id: UUID
    diff: Dict[str, Any]
    unwind_option: str = (
        "Manual unwind required: downstream effects must be addressed by a human operator."
    )


# ── Approval / rejection response schemas ─────────────────────────────────────

class ApprovalResponse(BaseModel):
    draft_id: UUID
    status: str
    message: str


class RejectionResponse(BaseModel):
    draft_id: UUID
    status: str
    message: str


class RollbackResponse(BaseModel):
    config_id: UUID
    restored_version: int
    message: str


class DeleteConfirmResponse(BaseModel):
    config_id: UUID
    status: str
    message: str
    unwind_reminder: str = (
        "All downstream effects must be unwound manually. No automated compensation will occur."
    )
