"""Data access layer for Page Config Drafter — flush()+refresh() only, never commit()."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import PageConfig, ProvenanceRecord, ScrollSection, SourcingTimelineEvent, VisualRepresentation


class PageConfigRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, page_config: PageConfig) -> PageConfig:
        self.session.add(page_config)
        await self.session.flush()
        await self.session.refresh(page_config)
        return page_config

    async def get_by_id(self, config_id: UUID) -> Optional[PageConfig]:
        result = await self.session.execute(
            select(PageConfig)
            .where(PageConfig.id == config_id)
            .options(
                selectinload(PageConfig.scroll_sections),
                selectinload(PageConfig.visual_representations),
                selectinload(PageConfig.sourcing_timeline_events),
                selectinload(PageConfig.provenance_records),
            )
        )
        return result.scalar_one_or_none()

    async def update(self, page_config: PageConfig) -> PageConfig:
        await self.session.flush()
        await self.session.refresh(page_config)
        return page_config

    async def delete(self, page_config: PageConfig) -> None:
        await self.session.delete(page_config)
        await self.session.flush()

    async def add_scroll_section(self, section: ScrollSection) -> ScrollSection:
        self.session.add(section)
        await self.session.flush()
        await self.session.refresh(section)
        return section

    async def add_visual_representation(self, vr: VisualRepresentation) -> VisualRepresentation:
        self.session.add(vr)
        await self.session.flush()
        await self.session.refresh(vr)
        return vr

    async def add_sourcing_event(self, event: SourcingTimelineEvent) -> SourcingTimelineEvent:
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event


class ProvenanceRecordRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def append(self, record: ProvenanceRecord) -> ProvenanceRecord:
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_by_config_ordered(self, config_id: UUID) -> List[ProvenanceRecord]:
        result = await self.session.execute(
            select(ProvenanceRecord)
            .where(ProvenanceRecord.page_config_id == config_id)
            .order_by(ProvenanceRecord.timestamp.desc())
        )
        return list(result.scalars().all())
