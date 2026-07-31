from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Enrollment, EnrollmentStatus, Session, SessionStatus
from utils.time_utils import utc_now


class EnrollmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_any(self, session_id: int, student_discord_id: int) -> Enrollment | None:
        """Busca la inscripción sin importar su estado (confirmada o
        cancelada). Sirve para reactivar una cancelada en vez de violar el
        UniqueConstraint intentando crear una fila nueva."""
        result = await self._session.execute(
            select(Enrollment).where(
                Enrollment.session_id == session_id,
                Enrollment.student_discord_id == student_discord_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_confirmed(self, session_id: int, student_discord_id: int) -> Enrollment | None:
        result = await self._session.execute(
            select(Enrollment).where(
                Enrollment.session_id == session_id,
                Enrollment.student_discord_id == student_discord_id,
                Enrollment.status == EnrollmentStatus.CONFIRMED,
            )
        )
        return result.scalar_one_or_none()

    async def count_confirmed(self, session_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Enrollment)
            .where(
                Enrollment.session_id == session_id,
                Enrollment.status == EnrollmentStatus.CONFIRMED,
            )
        )
        return result.scalar_one()

    async def add(self, *, session_id: int, student_discord_id: int) -> Enrollment:
        enrollment = Enrollment(session_id=session_id, student_discord_id=student_discord_id)
        self._session.add(enrollment)
        await self._session.flush()
        return enrollment

    async def set_status(self, enrollment: Enrollment, status: EnrollmentStatus) -> None:
        enrollment.status = status

    async def list_upcoming_for_student(self, student_discord_id: int) -> list[Enrollment]:
        """Sesiones futuras confirmadas de un estudiante, con `session`,
        `session.coach` y `session.course` ya cargados (hace falta para
        armar el mensaje de /mis-coachings sin volver a golpear la base)."""
        result = await self._session.execute(
            select(Enrollment)
            .join(Enrollment.session)
            .options(
                selectinload(Enrollment.session).selectinload(Session.coach),
                selectinload(Enrollment.session).selectinload(Session.course),
            )
            .where(
                Enrollment.student_discord_id == student_discord_id,
                Enrollment.status == EnrollmentStatus.CONFIRMED,
                Session.status == SessionStatus.SCHEDULED,
                Session.scheduled_at >= utc_now(),
            )
            .order_by(Session.scheduled_at)
        )
        return list(result.scalars().all())
