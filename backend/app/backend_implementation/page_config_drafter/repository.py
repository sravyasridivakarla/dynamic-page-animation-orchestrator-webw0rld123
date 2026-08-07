"""Data access layer for page config drafter."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .exceptions import ConfigNotFoundError
from .models import PageConfig, ScrollSection, SourcingTimelineEvent, VisualRepresentation


class PageConfigRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, config_id: UUID) -> PageConfig:
        stmt = (
            select(PageConfig)
            .where(PageConfig.id == config_id)
            .options(
                selectinload(PageConfig.scroll_sections),
                selectinload(PageConfig.visual_representations),
                selectinload(PageConfig.sourcing_timeline_events),
            )
        )
        result = await self.session.execute(stmt)
        config = result.scalar_one_or_none()
        if config is None:
            raise ConfigNotFoundError(f"Page config {config_id} not found")
        return config

    async def create(
        self,
        config: PageConfig,
        scroll_sections: List[ScrollSection],
        visual_representations: List[VisualRepresentation],
        events: List[SourcingTimelineEvent],
    ) -> PageConfig:
        self.session.add(config)
        await self.session.flush()

        for section in scroll_sections:
            section.config_id = config.id
            self.session.add(section)

        for visual_rep in visual_representations:
            visual_rep.config_id = config.id
            self.session.add(visual_rep)

        for event in events:
            event.config_id = config.id
            self.session.add(event)

        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def update(self, config_id: UUID, updates: dict) -> PageConfig:
        config = await self.get_by_id(config_id)
        for field, value in updates.items():
            setattr(config, field, value)
        await self.session.flush()
        await self.session.refresh(config)
        return config

    async def delete(self, config_id: UUID) -> None:
        config = await self.get_by_id(config_id)
        await self.session.delete(config)
        await self.session.flush()
