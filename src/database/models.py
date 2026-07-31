from __future__ import annotations

import enum
from datetime import datetime, time

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base
from utils.time_utils import utc_now


class SessionStatus(enum.Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EnrollmentStatus(enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class GuildSettings(Base):
    """Configuración global del bot.

    Como decidimos que el bot corre en un solo servidor de Discord, esta
    tabla tiene una única fila (id=1) en vez de una fila por servidor.
    roster_service / setup.py la usan para guardar cosas configurables sin
    tocar código, como en qué canal avisar que un coaching está por empezar.

    Los comandos de administración se restringen con el permiso nativo
    "Administrador" de Discord (ver bot.py / cogs/setup.py), así que no
    hace falta guardar un rol de admin acá.
    """

    __tablename__ = "guild_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    announcement_channel_id: Mapped[int | None] = mapped_column(default=None)


class Coach(Base):
    """Un coach registrado. `discord_user_id` es el ID numérico único que
    Discord le asigna a cada cuenta (un "snowflake"), no su nombre de
    usuario — el nombre puede cambiar, el ID nunca.
    """

    __tablename__ = "coaches"

    id: Mapped[int] = mapped_column(primary_key=True)
    discord_user_id: Mapped[int] = mapped_column(unique=True, index=True)
    display_name: Mapped[str]
    bio: Mapped[str | None] = mapped_column(default=None)
    active: Mapped[bool] = mapped_column(default=True)

    recurring_slots: Mapped[list["RecurringSlot"]] = relationship(back_populates="coach")
    sessions: Mapped[list["Session"]] = relationship(back_populates="coach")


class Course(Base):
    """Un curso/tipo de coaching ofrecido (ej. 'LoL - Jungla', 'Valorant - VOD review')."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    game: Mapped[str | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(default=None)
    active: Mapped[bool] = mapped_column(default=True)

    recurring_slots: Mapped[list["RecurringSlot"]] = relationship(back_populates="course")
    sessions: Mapped[list["Session"]] = relationship(back_populates="course")


class RecurringSlot(Base):
    """Plantilla de horario que se repite semanalmente.

    Es el único mecanismo para ambos casos de "recurrencia" que pediste:
    - capacity=1 -> agendamiento 1 a 1 (el estudiante reserva ese horario
      para sí solo).
    - capacity>1 -> evento grupal fijo (varios estudiantes se anotan al
      mismo horario, hasta llenar el cupo).

    De cada RecurringSlot activo, `scheduler_service` va a generar con
    anticipación instancias concretas en la tabla `sessions` (ej. las
    próximas 4 semanas) — eso es lo que el usuario realmente ve y agenda,
    no esta plantilla.
    """

    __tablename__ = "recurring_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))

    # 0 = lunes ... 6 = domingo (convención ISO 8601, misma que usa Python)
    day_of_week: Mapped[int]
    start_time: Mapped[time]
    duration_minutes: Mapped[int]
    capacity: Mapped[int] = mapped_column(default=1)

    # Canal de voz fijo (ya creado en el servidor) donde se conectan coach y
    # estudiantes cada semana. Opcional porque una sesión puede coordinarse
    # sin canal asignado (ej. por texto).
    voice_channel_id: Mapped[int | None] = mapped_column(default=None)

    active: Mapped[bool] = mapped_column(default=True)
    valid_from: Mapped[datetime | None] = mapped_column(default=None)
    valid_until: Mapped[datetime | None] = mapped_column(default=None)

    coach: Mapped["Coach"] = relationship(back_populates="recurring_slots")
    course: Mapped["Course"] = relationship(back_populates="recurring_slots")
    sessions: Mapped[list["Session"]] = relationship(back_populates="recurring_slot")


class Session(Base):
    """Una instancia concreta y agendable: un coach, un curso, una fecha y
    hora exactas (ej. "lunes 4 de agosto, 17:00hs").

    Normalmente se genera a partir de un RecurringSlot, pero
    `recurring_slot_id` es opcional para poder crear un evento puntual
    suelto (ej. una sesión especial de un solo día) sin necesitar una
    plantilla recurrente detrás.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        # Evita crear dos veces la sesión de "el próximo lunes 17hs" para el
        # mismo horario recurrente si dos personas agendan casi al mismo
        # tiempo (la segunda reutiliza la fila que ya existe).
        UniqueConstraint(
            "recurring_slot_id", "scheduled_at", name="uq_recurring_slot_occurrence"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recurring_slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_slots.id"), default=None
    )
    coach_id: Mapped[int] = mapped_column(ForeignKey("coaches.id"))
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"))

    # Se guarda en UTC; se convierte a settings.timezone recién al mostrarlo
    # al usuario. Guardar siempre en UTC evita bugs de horario de verano.
    scheduled_at: Mapped[datetime]
    duration_minutes: Mapped[int]
    capacity: Mapped[int] = mapped_column(default=1)
    status: Mapped[SessionStatus] = mapped_column(default=SessionStatus.SCHEDULED)
    announced_at: Mapped[datetime | None] = mapped_column(default=None)

    # Se copia del RecurringSlot al generar la sesión, para que quede fijo
    # aunque el horario recurrente cambie de canal después.
    voice_channel_id: Mapped[int | None] = mapped_column(default=None)

    recurring_slot: Mapped[RecurringSlot | None] = relationship(back_populates="sessions")
    coach: Mapped["Coach"] = relationship(back_populates="sessions")
    course: Mapped["Course"] = relationship(back_populates="sessions")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="session")


class Enrollment(Base):
    """Un estudiante anotado a una Session concreta.

    Para agendamiento 1 a 1 va a haber una sola Enrollment por Session;
    para eventos grupales, varias (hasta el `capacity` de la sesión).
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("session_id", "student_discord_id", name="uq_session_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id"))
    student_discord_id: Mapped[int] = mapped_column(index=True)
    status: Mapped[EnrollmentStatus] = mapped_column(default=EnrollmentStatus.CONFIRMED)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    session: Mapped["Session"] = relationship(back_populates="enrollments")
