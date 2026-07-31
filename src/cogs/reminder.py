from __future__ import annotations

from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from services.training_service import EnrollmentNotFoundError, TrainingService
from utils.time_utils import to_local
from utils.weekdays import DAY_NAMES


class ReminderCog(commands.Cog):
    """Comandos para que un usuario vea o cancele sus coachings agendados."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.training_service = TrainingService()

    @app_commands.command(
        name="mis-coachings", description="Muestra tus próximos coachings agendados"
    )
    async def mis_coachings(self, interaction: discord.Interaction) -> None:
        enrollments = await self.training_service.list_my_upcoming_sessions(interaction.user.id)
        if not enrollments:
            await interaction.response.send_message("No tenés coachings agendados.", ephemeral=True)
            return

        lineas = [
            f"- {enrollment.session.course.name} con {enrollment.session.coach.display_name} · "
            f"{self._format_datetime(enrollment.session.scheduled_at)}"
            for enrollment in enrollments
        ]
        await interaction.response.send_message("\n".join(lineas), ephemeral=True)

    @app_commands.command(
        name="cancelar-coaching", description="Cancela uno de tus coachings agendados"
    )
    @app_commands.describe(sesion="La sesión que querés cancelar")
    async def cancelar_coaching(self, interaction: discord.Interaction, sesion: int) -> None:
        try:
            await self.training_service.cancel_enrollment(
                session_id=sesion, student_discord_id=interaction.user.id
            )
        except EnrollmentNotFoundError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.send_message("Listo, cancelaste tu lugar en esa sesión.", ephemeral=True)

    @cancelar_coaching.autocomplete("sesion")
    async def _autocomplete_sesion(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[int]]:
        # Le muestra al usuario sus propios coachings agendados como
        # opciones, en vez de pedirle que escriba un id a mano.
        enrollments = await self.training_service.list_my_upcoming_sessions(interaction.user.id)
        choices = []
        for enrollment in enrollments:
            session_row = enrollment.session
            label = (
                f"{session_row.course.name} con {session_row.coach.display_name} · "
                f"{self._format_datetime(session_row.scheduled_at)}"
            )
            if current.lower() in label.lower():
                choices.append(app_commands.Choice(name=label[:100], value=session_row.id))
        return choices[:25]  # Discord no permite mostrar más de 25 opciones

    @staticmethod
    def _format_datetime(scheduled_at: datetime) -> str:
        local_time = to_local(scheduled_at)
        return f"{DAY_NAMES[local_time.weekday()]} {local_time.day:02d}/{local_time.month:02d} {local_time.strftime('%H:%M')}"


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ReminderCog(bot))
