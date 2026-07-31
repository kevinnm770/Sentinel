from __future__ import annotations

from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

from services.roster_service import (
    CoachNotFoundError,
    CourseNotFoundError,
    DuplicateCoachError,
    DuplicateCourseError,
    RecurringSlotNotFoundError,
    RosterService,
    SessionNotFoundError,
)
from utils.permissions import ADMIN_ONLY
from utils.time_parsing import parse_date_ddmmyyyy, parse_time_hhmm
from utils.time_utils import combine_local_to_utc, to_local
from utils.weekdays import DAY_NAMES, DAY_NUMBERS

# `Literal` con los 7 días hace que Discord le muestre al usuario un
# selector desplegable en vez de un campo de texto libre. Debe tener los
# mismos 7 valores que utils.weekdays.DAY_NAMES.
DayChoice = Literal["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


class RosterCog(commands.Cog):
    """Administración de coaches, cursos, horarios recurrentes y sesiones
    puntuales. Requiere permiso de Administrador."""

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
    session_group = app_commands.Group(
        name="sesion",
        description="Administrar sesiones puntuales (fecha exacta)",
        default_permissions=ADMIN_ONLY,
    )

    # ============================================================
    # coaches
    # ============================================================

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
        lineas = [
            f"- #{coach.id} {coach.display_name} (<@{coach.discord_user_id}>)" for coach in coaches
        ]
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)

    @coach_group.command(name="editar", description="Edita un coach existente")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        coach="El coach a editar",
        nuevo_nombre="Nuevo nombre a mostrar (opcional)",
        bio="Nueva descripción (opcional)",
        activo="Reactivar (True) o desactivar (False) el coach (opcional)",
    )
    async def coach_editar(
        self,
        interaction: discord.Interaction,
        coach: int,
        nuevo_nombre: str | None = None,
        bio: str | None = None,
        activo: bool | None = None,
    ) -> None:
        try:
            updated = await self.roster_service.edit_coach(
                coach_id=coach, display_name=nuevo_nombre, bio=bio, active=activo
            )
        except CoachNotFoundError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(f"Coach #{updated.id} actualizado.", ephemeral=True)

    @coach_group.command(name="eliminar", description="Desactiva un coach (no lo borra del historial)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(coach="El coach a desactivar")
    async def coach_eliminar(self, interaction: discord.Interaction, coach: int) -> None:
        try:
            await self.roster_service.deactivate_coach(coach)
        except CoachNotFoundError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(
            "Coach desactivado. Ya no va a ofrecerse para agendar; podés reactivarlo con /coach editar activo:True.",
            ephemeral=True,
        )

    # ============================================================
    # cursos
    # ============================================================

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
        lineas = [
            f"- #{course.id} {course.name}" + (f" ({course.game})" if course.game else "")
            for course in courses
        ]
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)

    @course_group.command(name="editar", description="Edita un curso existente")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        curso="El curso a editar",
        nuevo_nombre="Nuevo nombre (opcional)",
        juego="Nuevo juego asociado (opcional)",
        descripcion="Nueva descripción (opcional)",
        activo="Reactivar (True) o desactivar (False) el curso (opcional)",
    )
    async def curso_editar(
        self,
        interaction: discord.Interaction,
        curso: int,
        nuevo_nombre: str | None = None,
        juego: str | None = None,
        descripcion: str | None = None,
        activo: bool | None = None,
    ) -> None:
        try:
            updated = await self.roster_service.edit_course(
                course_id=curso, name=nuevo_nombre, game=juego, description=descripcion, active=activo
            )
        except CourseNotFoundError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(f"Curso #{updated.id} actualizado.", ephemeral=True)

    @course_group.command(name="eliminar", description="Desactiva un curso (no lo borra del historial)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(curso="El curso a desactivar")
    async def curso_eliminar(self, interaction: discord.Interaction, curso: int) -> None:
        try:
            await self.roster_service.deactivate_course(curso)
        except CourseNotFoundError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(
            "Curso desactivado. Ya no va a ofrecerse para agendar; podés reactivarlo con /curso editar activo:True.",
            ephemeral=True,
        )

    # ============================================================
    # horarios recurrentes
    # ============================================================

    @slot_group.command(name="agregar", description="Crea un horario recurrente semanal")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        coach="Nombre del coach, tal como aparece en /coach listar",
        curso="Nombre del curso, tal como aparece en /curso listar",
        dia="Día de la semana",
        hora="Hora de inicio en formato HH:MM, ej. 17:00",
        duracion_minutos="Duración de la sesión en minutos",
        cupo="Cantidad de estudiantes que pueden anotarse (1 = individual)",
        canal_voz="Canal de voz donde se van a conectar coach y estudiantes (opcional)",
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
        canal_voz: discord.VoiceChannel | None = None,
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
                voice_channel_id=canal_voz.id if canal_voz else None,
            )
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        canal_texto = f" · voz: {canal_voz.mention}" if canal_voz else ""
        await interaction.response.send_message(
            f"Horario creado: {coach_obj.display_name} · {course_obj.name} · {dia} {hora} "
            f"({duracion_minutos} min, cupo {cupo}){canal_texto}.",
            ephemeral=True,
        )

    @slot_group.command(name="listar", description="Lista los horarios recurrentes activos")
    @app_commands.checks.has_permissions(administrator=True)
    async def horario_listar(self, interaction: discord.Interaction) -> None:
        slots = await self.roster_service.list_active_recurring_slots()
        if not slots:
            await interaction.response.send_message("Todavía no hay horarios recurrentes.", ephemeral=True)
            return
        lineas = []
        for slot in slots:
            # <#id> es la sintaxis que Discord renderiza como mención de
            # canal clickeable, sin necesitar el objeto completo del canal.
            canal_texto = f" · voz: <#{slot.voice_channel_id}>" if slot.voice_channel_id else ""
            lineas.append(
                f"- #{slot.id} {slot.coach.display_name} · {slot.course.name} · "
                f"{DAY_NAMES[slot.day_of_week]} {slot.start_time.strftime('%H:%M')} "
                f"({slot.duration_minutes} min, cupo {slot.capacity}){canal_texto}"
            )
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)

    @slot_group.command(name="editar", description="Edita un horario recurrente existente")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        horario="El horario a editar",
        coach="Nuevo coach, tal como aparece en /coach listar (opcional)",
        curso="Nuevo curso, tal como aparece en /curso listar (opcional)",
        dia="Nuevo día de la semana (opcional)",
        hora="Nueva hora en formato HH:MM (opcional)",
        duracion_minutos="Nueva duración en minutos (opcional)",
        cupo="Nuevo cupo (opcional)",
        canal_voz="Nuevo canal de voz (opcional; no se puede quitar uno ya asignado desde acá)",
        activo="Reactivar (True) o desactivar (False) el horario (opcional)",
    )
    async def horario_editar(
        self,
        interaction: discord.Interaction,
        horario: int,
        coach: str | None = None,
        curso: str | None = None,
        dia: DayChoice | None = None,
        hora: str | None = None,
        duracion_minutos: int | None = None,
        cupo: int | None = None,
        canal_voz: discord.VoiceChannel | None = None,
        activo: bool | None = None,
    ) -> None:
        coach_id = None
        if coach is not None:
            coach_obj = await self.roster_service.find_coach_by_name(coach)
            if coach_obj is None:
                await interaction.response.send_message(
                    f"No encontré un coach llamado '{coach}'.", ephemeral=True
                )
                return
            coach_id = coach_obj.id

        course_id = None
        if curso is not None:
            course_obj = await self.roster_service.find_course_by_name(curso)
            if course_obj is None:
                await interaction.response.send_message(
                    f"No encontré un curso llamado '{curso}'.", ephemeral=True
                )
                return
            course_id = course_obj.id

        hora_parseada = None
        if hora is not None:
            try:
                hora_parseada = parse_time_hhmm(hora)
            except ValueError as error:
                await interaction.response.send_message(str(error), ephemeral=True)
                return

        try:
            await self.roster_service.edit_recurring_slot(
                slot_id=horario,
                coach_id=coach_id,
                course_id=course_id,
                day_of_week=DAY_NUMBERS[dia] if dia is not None else None,
                start_time=hora_parseada,
                duration_minutes=duracion_minutos,
                capacity=cupo,
                voice_channel_id=canal_voz.id if canal_voz else None,
                active=activo,
            )
        except (RecurringSlotNotFoundError, ValueError) as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(f"Horario #{horario} actualizado.", ephemeral=True)

    @slot_group.command(name="eliminar", description="Desactiva un horario recurrente")
    @app_commands.describe(horario="El horario a desactivar")
    @app_commands.checks.has_permissions(administrator=True)
    async def horario_eliminar(self, interaction: discord.Interaction, horario: int) -> None:
        try:
            await self.roster_service.deactivate_recurring_slot(horario)
        except RecurringSlotNotFoundError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(
            "Horario desactivado. Las sesiones ya agendadas de ese horario no se cancelan solas; "
            "usá /sesion eliminar si hace falta cancelar alguna en particular.",
            ephemeral=True,
        )

    # ============================================================
    # sesiones puntuales (fecha exacta, sin horario recurrente)
    # ============================================================

    @session_group.command(name="agregar", description="Crea una sesión puntual con fecha exacta")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        coach="Nombre del coach, tal como aparece en /coach listar",
        curso="Nombre del curso, tal como aparece en /curso listar",
        fecha="Fecha exacta en formato DD/MM/AAAA, ej. 15/08/2026",
        hora="Hora de inicio en formato HH:MM, ej. 17:00",
        duracion_minutos="Duración de la sesión en minutos",
        cupo="Cantidad de estudiantes que pueden anotarse (1 = individual)",
        canal_voz="Canal de voz donde se van a conectar coach y estudiantes (opcional)",
    )
    async def sesion_agregar(
        self,
        interaction: discord.Interaction,
        coach: str,
        curso: str,
        fecha: str,
        hora: str,
        duracion_minutos: int,
        cupo: int = 1,
        canal_voz: discord.VoiceChannel | None = None,
    ) -> None:
        try:
            fecha_parseada = parse_date_ddmmyyyy(fecha)
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

        scheduled_at = combine_local_to_utc(fecha_parseada, hora_parseada)
        try:
            session_row = await self.roster_service.create_standalone_session(
                coach_id=coach_obj.id,
                course_id=course_obj.id,
                scheduled_at=scheduled_at,
                duration_minutes=duracion_minutos,
                capacity=cupo,
                voice_channel_id=canal_voz.id if canal_voz else None,
            )
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        canal_texto = f" · voz: {canal_voz.mention}" if canal_voz else ""
        await interaction.response.send_message(
            f"Sesión #{session_row.id} creada: {coach_obj.display_name} · {course_obj.name} · "
            f"{fecha} {hora} ({duracion_minutos} min, cupo {cupo}){canal_texto}.",
            ephemeral=True,
        )

    @session_group.command(name="listar", description="Lista las próximas sesiones (recurrentes y puntuales)")
    @app_commands.checks.has_permissions(administrator=True)
    async def sesion_listar(self, interaction: discord.Interaction) -> None:
        sessions = await self.roster_service.list_upcoming_sessions()
        if not sessions:
            await interaction.response.send_message("No hay sesiones agendadas.", ephemeral=True)
            return
        lineas = []
        for session_row in sessions:
            local_time = to_local(session_row.scheduled_at)
            origen = "recurrente" if session_row.recurring_slot_id else "puntual"
            lineas.append(
                f"- #{session_row.id} {session_row.coach.display_name} · {session_row.course.name} · "
                f"{DAY_NAMES[local_time.weekday()]} {local_time.day:02d}/{local_time.month:02d} "
                f"{local_time.strftime('%H:%M')} ({origen})"
            )
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)

    @session_group.command(name="eliminar", description="Cancela una sesión agendada")
    @app_commands.describe(sesion="La sesión a cancelar")
    @app_commands.checks.has_permissions(administrator=True)
    async def sesion_eliminar(self, interaction: discord.Interaction, sesion: int) -> None:
        try:
            await self.roster_service.cancel_session(sesion)
        except SessionNotFoundError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message(f"Sesión #{sesion} cancelada.", ephemeral=True)

    # ============================================================
    # autocompletado
    # ============================================================

    @horario_agregar.autocomplete("coach")
    @horario_editar.autocomplete("coach")
    @sesion_agregar.autocomplete("coach")
    async def _autocomplete_coach_name(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        coaches = await self.roster_service.list_active_coaches()
        return [
            app_commands.Choice(name=coach.display_name, value=coach.display_name)
            for coach in coaches
            if current.lower() in coach.display_name.lower()
        ][:25]

    @horario_agregar.autocomplete("curso")
    @horario_editar.autocomplete("curso")
    @sesion_agregar.autocomplete("curso")
    async def _autocomplete_curso_name(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        courses = await self.roster_service.list_active_courses()
        return [
            app_commands.Choice(name=course.name, value=course.name)
            for course in courses
            if current.lower() in course.name.lower()
        ][:25]

    @coach_editar.autocomplete("coach")
    @coach_eliminar.autocomplete("coach")
    async def _autocomplete_coach_id(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        coaches = await self.roster_service.list_active_coaches()
        return [
            app_commands.Choice(name=f"#{coach.id} {coach.display_name}", value=coach.id)
            for coach in coaches
            if current.lower() in coach.display_name.lower()
        ][:25]

    @curso_editar.autocomplete("curso")
    @curso_eliminar.autocomplete("curso")
    async def _autocomplete_curso_id(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        courses = await self.roster_service.list_active_courses()
        return [
            app_commands.Choice(name=f"#{course.id} {course.name}", value=course.id)
            for course in courses
            if current.lower() in course.name.lower()
        ][:25]

    @horario_editar.autocomplete("horario")
    @horario_eliminar.autocomplete("horario")
    async def _autocomplete_horario_id(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        slots = await self.roster_service.list_active_recurring_slots()
        choices = []
        for slot in slots:
            label = (
                f"#{slot.id} {slot.coach.display_name} · {slot.course.name} · "
                f"{DAY_NAMES[slot.day_of_week]} {slot.start_time.strftime('%H:%M')}"
            )
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=slot.id))
        return choices[:25]

    @sesion_eliminar.autocomplete("sesion")
    async def _autocomplete_sesion_id(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        sessions = await self.roster_service.list_upcoming_sessions()
        choices = []
        for session_row in sessions:
            local_time = to_local(session_row.scheduled_at)
            label = (
                f"#{session_row.id} {session_row.coach.display_name} · {session_row.course.name} · "
                f"{local_time.day:02d}/{local_time.month:02d} {local_time.strftime('%H:%M')}"
            )
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=session_row.id))
        return choices[:25]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RosterCog(bot))
