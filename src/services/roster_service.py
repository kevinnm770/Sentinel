from __future__ import annotations

from datetime import time

from database.database import get_session
from database.models import Coach, Course, RecurringSlot
from database.repositories.coach_repository import CoachRepository
from database.repositories.course_repository import CourseRepository
from database.repositories.recurring_slot_repository import RecurringSlotRepository


class DuplicateCoachError(Exception):
    """Ya existe un coach registrado para ese usuario de Discord."""


class DuplicateCourseError(Exception):
    """Ya existe un curso con ese nombre."""


class RosterService:
    """Lógica de negocio para administrar coaches, cursos y horarios recurrentes.

    Cada método abre y cierra su propia sesión de base de datos: son
    operaciones independientes entre sí (registrar un coach no necesita
    compartir transacción con listar cursos), así que no hace falta que el
    caller (el cog) maneje sesiones directamente.
    """

    async def register_coach(
        self, *, discord_user_id: int, display_name: str, bio: str | None = None
    ) -> Coach:
        async with get_session() as session:
            repo = CoachRepository(session)
            if await repo.get_by_discord_id(discord_user_id) is not None:
                raise DuplicateCoachError("Ese usuario ya está registrado como coach.")
            return await repo.add(discord_user_id=discord_user_id, display_name=display_name, bio=bio)

    async def list_active_coaches(self) -> list[Coach]:
        async with get_session() as session:
            return await CoachRepository(session).list_active()

    async def find_coach_by_name(self, display_name: str) -> Coach | None:
        async with get_session() as session:
            return await CoachRepository(session).get_by_display_name(display_name)

    async def register_course(
        self, *, name: str, game: str | None = None, description: str | None = None
    ) -> Course:
        async with get_session() as session:
            repo = CourseRepository(session)
            if await repo.get_by_name(name) is not None:
                raise DuplicateCourseError(f"Ya existe un curso llamado '{name}'.")
            return await repo.add(name=name, game=game, description=description)

    async def list_active_courses(self) -> list[Course]:
        async with get_session() as session:
            return await CourseRepository(session).list_active()

    async def find_course_by_name(self, name: str) -> Course | None:
        async with get_session() as session:
            return await CourseRepository(session).get_by_name(name)

    async def add_recurring_slot(
        self,
        *,
        coach_id: int,
        course_id: int,
        day_of_week: int,
        start_time: time,
        duration_minutes: int,
        capacity: int = 1,
    ) -> RecurringSlot:
        if not 0 <= day_of_week <= 6:
            raise ValueError("El día debe estar entre lunes (0) y domingo (6).")
        if duration_minutes <= 0:
            raise ValueError("La duración debe ser mayor a 0 minutos.")
        if capacity <= 0:
            raise ValueError("El cupo debe ser mayor a 0.")

        async with get_session() as session:
            return await RecurringSlotRepository(session).add(
                coach_id=coach_id,
                course_id=course_id,
                day_of_week=day_of_week,
                start_time=start_time,
                duration_minutes=duration_minutes,
                capacity=capacity,
            )

    async def list_active_recurring_slots(self) -> list[RecurringSlot]:
        async with get_session() as session:
            return await RecurringSlotRepository(session).list_active()
