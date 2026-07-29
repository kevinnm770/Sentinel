from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from services.roster_service import DuplicateCoachError, DuplicateCourseError, RosterService
from utils.permissions import ADMIN_ONLY
from utils.time_parsing import parse_time_hhmm

# Mapeo entre el nombre de día que ve el usuario (en español, como en el
# selector del comando) y el número 0-6 que se guarda en la base de datos.
DAY_NUMBERS: dict[str, int] = {
    "Lunes": 0,
    "Martes": 1,
    "Miércoles": 2,
    "Jueves": 3,
    "Viernes": 4,
    "Sábado": 5,
    "Domingo": 6,
}
DAY_NAMES: dict[int, str] = {number: name for name, number in DAY_NUMBERS.items()}

# `Literal` con los 7 días hace que Discord le muestre al usuario un
# selector desplegable en vez de un campo de texto libre.
DayChoice = Literal["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class RosterCog(commands.Cog):
    """Administración de coaches, cursos y horarios recurrentes. Requiere permiso de Administrador."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.roster_service = RosterService()

    coach_group = app_commands.Group(
        name="coach", description="Administrar coaches", default_permissions=ADMIN_ONLY
    )
    course_group = app_commands.Group(
        name="curso", description="Administrar cursos", default_permissions=ADMIN_ONLY
    )
    slot_group = app_commands.Group(
        name="horario",
        description="Administrar horarios recurrentes",
        default_permissions=ADMIN_ONLY,
    )

    # --- coaches ---

    @coach_group.command(name="agregar", description="Registra un nuevo coach")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(usuario="Usuario de Discord del coach", bio="Descripción breve (opcional)")
    async def coach_agregar(
        self, interaction: discord.Interaction, usuario: discord.Member, bio: str | None = None
    ) -> None:
        try:
            await self.roster_service.register_coach(
                discord_user_id=usuario.id, display_name=usuario.display_name, bio=bio
            )
        except DuplicateCoachError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(f"Coach {usuario.mention} registrado.", ephemeral=True)

    @coach_group.command(name="listar", description="Lista los coaches activos")
    @app_commands.checks.has_permissions(administrator=True)
    async def coach_listar(self, interaction: discord.Interaction) -> None:
        coaches = await self.roster_service.list_active_coaches()
        if not coaches:
            await interaction.response.send_message("Todavía no hay coaches registrados.", ephemeral=True)
            return
        lineas = [f"- {coach.display_name} (<@{coach.discord_user_id}>)" for coach in coaches]
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)

    # --- cursos ---

    @course_group.command(name="agregar", description="Registra un nuevo curso")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        nombre="Nombre del curso",
        juego="Juego asociado (opcional)",
        descripcion="Descripción breve (opcional)",
    )
    async def curso_agregar(
        self,
        interaction: discord.Interaction,
        nombre: str,
        juego: str | None = None,
        descripcion: str | None = None,
    ) -> None:
        try:
            await self.roster_service.register_course(name=nombre, game=juego, description=descripcion)
        except DuplicateCourseError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(f"Curso '{nombre}' registrado.", ephemeral=True)

    @course_group.command(name="listar", description="Lista los cursos activos")
    @app_commands.checks.has_permissions(administrator=True)
    async def curso_listar(self, interaction: discord.Interaction) -> None:
        courses = await self.roster_service.list_active_courses()
        if not courses:
            await interaction.response.send_message("Todavía no hay cursos registrados.", ephemeral=True)
            return
        lineas = [f"- {course.name}" + (f" ({course.game})" if course.game else "") for course in courses]
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)

    # --- horarios recurrentes ---

    @slot_group.command(name="agregar", description="Crea un horario recurrente semanal")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        coach="Nombre del coach, tal como aparece en /coach listar",
        curso="Nombre del curso, tal como aparece en /curso listar",
        dia="Día de la semana",
        hora="Hora de inicio en formato HH:MM, ej. 17:00",
        duracion_minutos="Duración de la sesión en minutos",
        cupo="Cantidad de estudiantes que pueden anotarse (1 = individual)",
    )
    async def horario_agregar(
        self,
        interaction: discord.Interaction,
        coach: str,
        curso: str,
        dia: DayChoice,
        hora: str,
        duracion_minutos: int,
        cupo: int = 1,
    ) -> None:
        try:
            hora_parseada = parse_time_hhmm(hora)
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        coach_obj = await self.roster_service.find_coach_by_name(coach)
        if coach_obj is None:
            await interaction.response.send_message(
                f"No encontré un coach llamado '{coach}'. Usá /coach listar para ver los nombres exactos.",
                ephemeral=True,
            )
            return

        course_obj = await self.roster_service.find_course_by_name(curso)
        if course_obj is None:
            await interaction.response.send_message(
                f"No encontré un curso llamado '{curso}'. Usá /curso listar para ver los nombres exactos.",
                ephemeral=True,
            )
            return

        try:
            await self.roster_service.add_recurring_slot(
                coach_id=coach_obj.id,
                course_id=course_obj.id,
                day_of_week=DAY_NUMBERS[dia],
                start_time=hora_parseada,
                duration_minutes=duracion_minutos,
                capacity=cupo,
            )
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        await interaction.response.send_message(
            f"Horario creado: {coach_obj.display_name} · {course_obj.name} · {dia} {hora} "
            f"({duracion_minutos} min, cupo {cupo}).",
            ephemeral=True,
        )

    @slot_group.command(name="listar", description="Lista los horarios recurrentes activos")
    @app_commands.checks.has_permissions(administrator=True)
    async def horario_listar(self, interaction: discord.Interaction) -> None:
        slots = await self.roster_service.list_active_recurring_slots()
        if not slots:
            await interaction.response.send_message("Todavía no hay horarios recurrentes.", ephemeral=True)
            return
        lineas = [
            f"- {slot.coach.display_name} · {slot.course.name} · {DAY_NAMES[slot.day_of_week]} "
            f"{slot.start_time.strftime('%H:%M')} ({slot.duration_minutes} min, cupo {slot.capacity})"
            for slot in slots
        ]
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RosterCog(bot))
