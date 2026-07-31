from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from config.settings import settings
from database.database import get_session
from database.models import Course, Enrollment, EnrollmentStatus
from database.repositories.course_repository import CourseRepository
from database.repositories.enrollment_repository import EnrollmentRepository
from database.repositories.recurring_slot_repository import RecurringSlotRepository
from database.repositories.session_repository import SessionRepository


class SlotFullError(Exception):
    """Ese horario ya llegó a su cupo máximo."""


class AlreadyEnrolledError(Exception):
    """El usuario ya está anotado a esa sesión."""


class SlotNotFoundError(Exception):
    """El horario recurrente no existe o fue desactivado."""


class EnrollmentNotFoundError(Exception):
    """El usuario no tiene una inscripción confirmada para esa sesión."""


@dataclass
class SlotAvailability:
    """Un horario disponible, con la info lista para mostrarse en Discord."""

    recurring_slot_id: int
    coach_name: str
    course_name: str
    day_of_week: int
    start_time: time
    next_occurrence: datetime  # UTC, naive (ver utils/time_utils.py)
    capacity: int
    enrolled_count: int

    @property
    def spots_left(self) -> int:
        return self.capacity - self.enrolled_count


def _next_occurrence(day_of_week: int, start_time: time) -> datetime:
    """Calcula la próxima fecha/hora en que cae ese día de la semana a esa
    hora, usando la zona horaria única del servidor, y la devuelve en UTC
    sin tzinfo (la convención que usa toda la base de datos).

    Si hoy es ese día pero la hora ya pasó, salta a la semana siguiente.
    """
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz)
    days_ahead = (day_of_week - now_local.weekday()) % 7
    candidate = datetime.combine(
        (now_local + timedelta(days=days_ahead)).date(), start_time, tzinfo=tz
    )
    if candidate <= now_local:
        candidate += timedelta(days=7)
    return candidate.astimezone(timezone.utc).replace(tzinfo=None)


class TrainingService:
    """Lógica de negocio del agendamiento: qué horarios hay disponibles y
    cómo se anota un estudiante a uno."""

    async def list_active_courses(self) -> list[Course]:
        async with get_session() as session:
            return await CourseRepository(session).list_active()

    async def list_available_slots(self, course_id: int) -> list[SlotAvailability]:
        async with get_session() as session:
            slot_repo = RecurringSlotRepository(session)
            session_repo = SessionRepository(session)
            enrollment_repo = EnrollmentRepository(session)

            # Un horario activo puede quedar "huérfano" si su coach o curso
            # se desactivó por separado (/coach eliminar, /curso eliminar);
            # en ese caso no debería seguir ofreciéndose para agendar.
            course_slots = [
                slot
                for slot in await slot_repo.list_active()
                if slot.course_id == course_id and slot.coach.active and slot.course.active
            ]

            availability: list[SlotAvailability] = []
            for slot in course_slots:
                occurrence = _next_occurrence(slot.day_of_week, slot.start_time)
                existing = await session_repo.get_by_slot_and_time(slot.id, occurrence)
                enrolled_count = (
                    await enrollment_repo.count_confirmed(existing.id) if existing else 0
                )
                if enrolled_count >= slot.capacity:
                    continue  # ya está lleno, no lo mostramos como opción
                availability.append(
                    SlotAvailability(
                        recurring_slot_id=slot.id,
                        coach_name=slot.coach.display_name,
                        course_name=slot.course.name,
                        day_of_week=slot.day_of_week,
                        start_time=slot.start_time,
                        next_occurrence=occurrence,
                        capacity=slot.capacity,
                        enrolled_count=enrolled_count,
                    )
                )
            return availability

    async def book(self, *, recurring_slot_id: int, student_discord_id: int) -> SlotAvailability:
        async with get_session() as session:
            slot_repo = RecurringSlotRepository(session)
            session_repo = SessionRepository(session)
            enrollment_repo = EnrollmentRepository(session)

            slot = await slot_repo.get_by_id(recurring_slot_id)
            if slot is None or not slot.active or not slot.coach.active or not slot.course.active:
                raise SlotNotFoundError("Ese horario ya no está disponible.")

            occurrence = _next_occurrence(slot.day_of_week, slot.start_time)
            session_row = await session_repo.get_or_create_for_slot(slot, occurrence)

            if await enrollment_repo.get_confirmed(session_row.id, student_discord_id) is not None:
                raise AlreadyEnrolledError("Ya estás anotado a esta sesión.")

            enrolled_count = await enrollment_repo.count_confirmed(session_row.id)
            if enrolled_count >= session_row.capacity:
                raise SlotFullError("Ese horario se acaba de llenar. Probá con otro.")

            # Si ya se había anotado y después canceló, reactivamos esa
            # misma fila en vez de crear una nueva (el UniqueConstraint de
            # (session_id, student_discord_id) no lo permitiría).
            existing = await enrollment_repo.get_any(session_row.id, student_discord_id)
            if existing is not None:
                await enrollment_repo.set_status(existing, EnrollmentStatus.CONFIRMED)
            else:
                await enrollment_repo.add(session_id=session_row.id, student_discord_id=student_discord_id)

            return SlotAvailability(
                recurring_slot_id=slot.id,
                coach_name=slot.coach.display_name,
                course_name=slot.course.name,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                next_occurrence=occurrence,
                capacity=session_row.capacity,
                enrolled_count=enrolled_count + 1,
            )

    async def list_my_upcoming_sessions(self, student_discord_id: int) -> list[Enrollment]:
        async with get_session() as session:
            return await EnrollmentRepository(session).list_upcoming_for_student(student_discord_id)

    async def cancel_enrollment(self, *, session_id: int, student_discord_id: int) -> None:
        async with get_session() as session:
            enrollment_repo = EnrollmentRepository(session)
            enrollment = await enrollment_repo.get_confirmed(session_id, student_discord_id)
            if enrollment is None:
                raise EnrollmentNotFoundError("No estás anotado a esa sesión (o ya la cancelaste).")
            await enrollment_repo.set_status(enrollment, EnrollmentStatus.CANCELLED)
