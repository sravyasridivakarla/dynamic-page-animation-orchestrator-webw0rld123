"""Data access layer for page config drafter."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .exceptions import ConfigNotFoundError
from .models import PageConfig, ScrollSection, SourcingTimelineEvent, VisualRepresentation


class PageConfigRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, config_id: uuid.UUID) -> PageConfig:
        result = await self.db.execute(
            select(PageConfig)
            .where(PageConfig.id == config_id)
            .options(
                selectinload(PageConfig.scroll_sections),
                selectinload(PageConfig.visual_representations),
                selectinload(PageConfig.sourcing_timeline_events),
            )
        )
        config = result.scalar_one_or_none()
        if config is None:
            raise ConfigNotFoundError(config_id)
        return config

    async def create(
        self,
        config: PageConfig,
        scroll_sections: list[ScrollSection],
        visual_reps: list[VisualRepresentation],
        events: list[SourcingTimelineEvent],
    ) -> PageConfig:
        self.db.add(config)
        await self.db.flush()
        for section in scroll_sections:
            section.config_id = config.id
            self.db.add(section)
        for vr in visual_reps:
            vr.config_id = config.id
            self.db.add(vr)
        for event in events:
            event.config_id = config.id
            self.db.add(event)
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def update(self, config_id: uuid.UUID, updates: dict) -> PageConfig:
        config = await self.get_by_id(config_id)
        for field, value in updates.items():
            setattr(config, field, value)
        await self.db.flush()
        await self.db.refresh(config)
        return config

    async def delete(self, config_id: uuid.UUID) -> None:
        config = await self.get_by_id(config_id)
        await self.db.delete(config)
        await self.db.flush()
