from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import RecurringSlot, Session, SessionStatus
from utils.time_utils import utc_now


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, session_id: int) -> Session | None:
        result = await self._session.execute(
            select(Session)
            .options(selectinload(Session.coach), selectinload(Session.course))
            .where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def create_standalone(
        self,
        *,
        coach_id: int,
        course_id: int,
        scheduled_at: datetime,
        duration_minutes: int,
        capacity: int = 1,
        voice_channel_id: int | None = None,
    ) -> Session:
        """Crea una sesión puntual con fecha exacta, sin plantilla
        recurrente detrás (`recurring_slot_id` queda en None)."""
        new_session = Session(
            recurring_slot_id=None,
            coach_id=coach_id,
            course_id=course_id,
            scheduled_at=scheduled_at,
            duration_minutes=duration_minutes,
            capacity=capacity,
            voice_channel_id=voice_channel_id,
        )
        self._session.add(new_session)
        await self._session.flush()
        return new_session

    async def list_upcoming(self) -> list[Session]:
        result = await self._session.execute(
            select(Session)
            .options(selectinload(Session.coach), selectinload(Session.course))
            .where(
                Session.status == SessionStatus.SCHEDULED,
                Session.scheduled_at >= utc_now(),
            )
            .order_by(Session.scheduled_at)
        )
        return list(result.scalars().all())

    async def cancel(self, session_id: int) -> None:
        session_row = await self._session.get(Session, session_id)
        if session_row is not None:
            session_row.status = SessionStatus.CANCELLED

    async def get_by_slot_and_time(
        self, recurring_slot_id: int, scheduled_at: datetime
    ) -> Session | None:
        result = await self._session.execute(
            select(Session).where(
                Session.recurring_slot_id == recurring_slot_id,
                Session.scheduled_at == scheduled_at,
            )
        )
        return result.scalar_one_or_none()

    async def create_from_slot(self, slot: RecurringSlot, scheduled_at: datetime) -> Session:
        """Materializa una ocurrencia concreta a partir de una plantilla
        recurrente, copiando los datos que en ese momento tenía el slot
        (coach, duración, cupo, canal de voz)."""
        new_session = Session(
            recurring_slot_id=slot.id,
            coach_id=slot.coach_id,
            course_id=slot.course_id,
            scheduled_at=scheduled_at,
            duration_minutes=slot.duration_minutes,
            capacity=slot.capacity,
            voice_channel_id=slot.voice_channel_id,
        )
        self._session.add(new_session)
        await self._session.flush()
        return new_session

    async def get_or_create_for_slot(self, slot: RecurringSlot, scheduled_at: datetime) -> Session:
        existing = await self.get_by_slot_and_time(slot.id, scheduled_at)
        if existing is not None:
            return existing
        return await self.create_from_slot(slot, scheduled_at)

    async def list_upcoming_unannounced(self, *, within_minutes: int) -> list[Session]:
        """Sesiones agendadas que arrancan dentro de `within_minutes` y
        todavía no se avisaron. `coach`, `course` y `enrollments` vienen
        precargados porque el scheduler los va a necesitar para armar el
        mensaje y gestionar el canal de voz."""
        now = utc_now()
        threshold = now + timedelta(minutes=within_minutes)
        result = await self._session.execute(
            select(Session)
            .options(
                selectinload(Session.coach),
                selectinload(Session.course),
                selectinload(Session.enrollments),
            )
            .where(
                Session.status == SessionStatus.SCHEDULED,
                Session.announced_at.is_(None),
                Session.scheduled_at >= now,
                Session.scheduled_at <= threshold,
            )
        )
        return list(result.scalars().all())

    async def mark_announced(self, session_id: int) -> None:
        session_row = await self._session.get(Session, session_id)
        if session_row is not None:
            session_row.announced_at = utc_now()

    async def list_due_for_completion(self) -> list[Session]:
        """Sesiones agendadas cuyo horario (inicio + duración) ya pasó,
        para cerrarlas y liberar el canal de voz."""
        now = utc_now()
        result = await self._session.execute(
            select(Session).where(Session.status == SessionStatus.SCHEDULED)
        )
        return [
            session_row
            for session_row in result.scalars().all()
            if session_row.scheduled_at + timedelta(minutes=session_row.duration_minutes) <= now
        ]

    async def mark_completed(self, session_id: int) -> None:
        session_row = await self._session.get(Session, session_id)
        if session_row is not None:
            session_row.status = SessionStatus.COMPLETED
