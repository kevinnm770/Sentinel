from __future__ import annotations

from datetime import datetime, time

from database.database import get_session
from database.models import Coach, Course, RecurringSlot, Session
from database.repositories.coach_repository import CoachRepository
from database.repositories.course_repository import CourseRepository
from database.repositories.recurring_slot_repository import RecurringSlotRepository
from database.repositories.session_repository import SessionRepository
from utils.time_utils import utc_now


class DuplicateCoachError(Exception):
    """Ya existe un coach registrado para ese usuario de Discord."""


class DuplicateCourseError(Exception):
    """Ya existe un curso con ese nombre."""


class CoachNotFoundError(Exception):
    """No existe un coach con ese id."""


class CourseNotFoundError(Exception):
    """No existe un curso con ese id."""


class RecurringSlotNotFoundError(Exception):
    """No existe un horario recurrente con ese id."""


class SessionNotFoundError(Exception):
    """No existe una sesión con ese id."""


class RosterService:
    """Lógica de negocio para administrar coaches, cursos, horarios
    recurrentes y sesiones puntuales.

    Cada método abre y cierra su propia sesión de base de datos: son
    operaciones independientes entre sí (registrar un coach no necesita
    compartir transacción con listar cursos), así que no hace falta que el
    caller (el cog) maneje sesiones directamente.

    "Eliminar" en todo este archivo es un borrado lógico (`active = False`),
    no un DELETE físico: un coach o curso ya puede tener horarios y
    sesiones históricas asociadas, y borrarlo de verdad las dejaría
    huérfanas. Desactivar se puede revertir con `editar`.
    """

    # --- coaches ---

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

    async def edit_coach(
        self,
        *,
        coach_id: int,
        display_name: str | None = None,
        bio: str | None = None,
        active: bool | None = None,
    ) -> Coach:
        async with get_session() as session:
            coach = await CoachRepository(session).get_by_id(coach_id)
            if coach is None:
                raise CoachNotFoundError("No encontré ese coach.")
            if display_name is not None:
                coach.display_name = display_name
            if bio is not None:
                coach.bio = bio
            if active is not None:
                coach.active = active
            return coach

    async def deactivate_coach(self, coach_id: int) -> None:
        async with get_session() as session:
            coach = await CoachRepository(session).get_by_id(coach_id)
            if coach is None:
                raise CoachNotFoundError("No encontré ese coach.")
            coach.active = False

    # --- cursos ---

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

    async def edit_course(
        self,
        *,
        course_id: int,
        name: str | None = None,
        game: str | None = None,
        description: str | None = None,
        active: bool | None = None,
    ) -> Course:
        async with get_session() as session:
            course = await CourseRepository(session).get_by_id(course_id)
            if course is None:
                raise CourseNotFoundError("No encontré ese curso.")
            if name is not None:
                course.name = name
            if game is not None:
                course.game = game
            if description is not None:
                course.description = description
            if active is not None:
                course.active = active
            return course

    async def deactivate_course(self, course_id: int) -> None:
        async with get_session() as session:
            course = await CourseRepository(session).get_by_id(course_id)
            if course is None:
                raise CourseNotFoundError("No encontré ese curso.")
            course.active = False

    # --- horarios recurrentes ---

    async def add_recurring_slot(
        self,
        *,
        coach_id: int,
        course_id: int,
        day_of_week: int,
        start_time: time,
        duration_minutes: int,
        capacity: int = 1,
        voice_channel_id: int | None = None,
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
                voice_channel_id=voice_channel_id,
            )

    async def list_active_recurring_slots(self) -> list[RecurringSlot]:
        async with get_session() as session:
            return await RecurringSlotRepository(session).list_active()

    async def edit_recurring_slot(
        self,
        *,
        slot_id: int,
        coach_id: int | None = None,
        course_id: int | None = None,
        day_of_week: int | None = None,
        start_time: time | None = None,
        duration_minutes: int | None = None,
        capacity: int | None = None,
        voice_channel_id: int | None = None,
        active: bool | None = None,
    ) -> RecurringSlot:
        if day_of_week is not None and not 0 <= day_of_week <= 6:
            raise ValueError("El día debe estar entre lunes (0) y domingo (6).")
        if duration_minutes is not None and duration_minutes <= 0:
            raise ValueError("La duración debe ser mayor a 0 minutos.")
        if capacity is not None and capacity <= 0:
            raise ValueError("El cupo debe ser mayor a 0.")

        async with get_session() as session:
            slot = await RecurringSlotRepository(session).get_by_id(slot_id)
            if slot is None:
                raise RecurringSlotNotFoundError("No encontré ese horario.")
            if coach_id is not None:
                slot.coach_id = coach_id
            if course_id is not None:
                slot.course_id = course_id
            if day_of_week is not None:
                slot.day_of_week = day_of_week
            if start_time is not None:
                slot.start_time = start_time
            if duration_minutes is not None:
                slot.duration_minutes = duration_minutes
            if capacity is not None:
                slot.capacity = capacity
            if voice_channel_id is not None:
                slot.voice_channel_id = voice_channel_id
            if active is not None:
                slot.active = active
            return slot

    async def deactivate_recurring_slot(self, slot_id: int) -> None:
        async with get_session() as session:
            slot = await RecurringSlotRepository(session).get_by_id(slot_id)
            if slot is None:
                raise RecurringSlotNotFoundError("No encontré ese horario.")
            slot.active = False

    # --- sesiones puntuales (fecha exacta, sin horario recurrente detrás) ---

    async def create_standalone_session(
        self,
        *,
        coach_id: int,
        course_id: int,
        scheduled_at: datetime,
        duration_minutes: int,
        capacity: int = 1,
        voice_channel_id: int | None = None,
    ) -> Session:
        if duration_minutes <= 0:
            raise ValueError("La duración debe ser mayor a 0 minutos.")
        if capacity <= 0:
            raise ValueError("El cupo debe ser mayor a 0.")
        if scheduled_at <= utc_now():
            raise ValueError("La fecha y hora tienen que ser en el futuro.")

        async with get_session() as session:
            return await SessionRepository(session).create_standalone(
                coach_id=coach_id,
                course_id=course_id,
                scheduled_at=scheduled_at,
                duration_minutes=duration_minutes,
                capacity=capacity,
                voice_channel_id=voice_channel_id,
            )

    async def list_upcoming_sessions(self) -> list[Session]:
        async with get_session() as session:
            return await SessionRepository(session).list_upcoming()

    async def cancel_session(self, session_id: int) -> None:
        async with get_session() as session:
            repo = SessionRepository(session)
            session_row = await repo.get_by_id(session_id)
            if session_row is None:
                raise SessionNotFoundError("No encontré esa sesión.")
            await repo.cancel(session_id)
