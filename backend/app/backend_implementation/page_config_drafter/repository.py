"""Data access layer for Page Config Drafter — flush()+refresh() only, never commit()."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.backend_implementation.page_config_drafter.models import (
    ActionType,
    PageConfig,
    ProvenanceRecord,
    ScrollSection,
    SourcingTimelineEvent,
    VisualRepresentation,
    WorkflowState,
)


class PageConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, config_id: UUID) -> Optional[PageConfig]:
        result = await self.db.execute(
            select(PageConfig)
            .options(
                selectinload(PageConfig.scroll_sections),
                selectinload(PageConfig.visual_representations),
                selectinload(PageConfig.sourcing_timeline_events),
                selectinload(PageConfig.provenance_records),
            )
            .where(PageConfig.id == config_id)
        )
        return result.scalar_one_or_none()

    async def get_by_product_id(self, product_id: str) -> Optional[PageConfig]:
        result = await self.db.execute(
            select(PageConfig)
            .options(
                selectinload(PageConfig.scroll_sections),
                selectinload(PageConfig.visual_representations),
                selectinload(PageConfig.sourcing_timeline_events),
            )
            .where(PageConfig.product_id == product_id)
        )
        return result.scalar_one_or_none()

    async def create_page_config(self, product_id: str) -> PageConfig:
        config = PageConfig(
            product_id=product_id,
            workflow_state=WorkflowState.draft,
            version=1,
        )
        self.db.add(config)
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def update_workflow_state(self, config: PageConfig, state: WorkflowState) -> PageConfig:
        config.workflow_state = state
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def increment_version(self, config: PageConfig) -> PageConfig:
        config.version = config.version + 1
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def create_scroll_section(self, page_config_id: UUID, order: int, content: str) -> ScrollSection:
        section = ScrollSection(page_config_id=page_config_id, order=order, content=content)
        self.db.add(section)
        await self.db.flush()
        await self.db.refresh(section)
        return section

    async def create_visual_representation(self, page_config_id: UUID, type: str, url: str) -> VisualRepresentation:
        vr = VisualRepresentation(page_config_id=page_config_id, type=type, url=url)
        self.db.add(vr)
        await self.db.flush()
        await self.db.refresh(vr)
        return vr

    async def create_sourcing_timeline_event(
        self, page_config_id: UUID, event_type: str, date, validated: bool
    ) -> SourcingTimelineEvent:
        event = SourcingTimelineEvent(
            page_config_id=page_config_id,
            event_type=event_type,
            date=date,
            validated=validated,
        )
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def create_provenance_record(
        self,
        page_config_id: UUID,
        action_type: ActionType,
        inputs: Optional[dict] = None,
        sources: Optional[dict] = None,
        reasoning_trace: Optional[str] = None,
        diff_presented: Optional[dict] = None,
        human_decision: Optional[str] = None,
        justification: Optional[str] = None,
    ) -> ProvenanceRecord:
        record = ProvenanceRecord(
            page_config_id=page_config_id,
            action_type=action_type,
            inputs=inputs,
            sources=sources,
            reasoning_trace=reasoning_trace,
            diff_presented=diff_presented,
            human_decision=human_decision,
            justification=justification,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    async def get_provenance_records(self, config_id: UUID) -> List[ProvenanceRecord]:
        result = await self.db.execute(
            select(ProvenanceRecord)
            .where(ProvenanceRecord.page_config_id == config_id)
            .order_by(ProvenanceRecord.timestamp)
        )
        return list(result.scalars().all())

    async def delete_page_config(self, config: PageConfig) -> None:
        await self.db.delete(config)
        await self.db.flush()
