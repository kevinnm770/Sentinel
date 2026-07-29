from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import RecurringSlot


class RecurringSlotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        coach_id: int,
        course_id: int,
        day_of_week: int,
        start_time: time,
        duration_minutes: int,
        capacity: int = 1,
    ) -> RecurringSlot:
        slot = RecurringSlot(
            coach_id=coach_id,
            course_id=course_id,
            day_of_week=day_of_week,
            start_time=start_time,
            duration_minutes=duration_minutes,
            capacity=capacity,
        )
        self._session.add(slot)
        await self._session.flush()
        return slot

    async def list_active(self) -> list[RecurringSlot]:
        # `selectinload` trae coach y course en la misma operación (2 queries
        # extra, no N+1). Es necesario porque el resultado se usa después de
        # cerrar la sesión (al armar el mensaje de Discord): sin esto,
        # acceder a `slot.coach` en ese momento fallaría porque ya no hay
        # una sesión abierta para ir a buscarlo a la base de datos.
        result = await self._session.execute(
            select(RecurringSlot)
            .options(selectinload(RecurringSlot.coach), selectinload(RecurringSlot.course))
            .where(RecurringSlot.active.is_(True))
        )
        return list(result.scalars().all())
