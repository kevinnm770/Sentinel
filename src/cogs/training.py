from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.training_service import TrainingService
from ui.booking_views import CourseSelectView, SlotSelectView


class TrainingCog(commands.Cog):
    """Comando para que cualquier usuario agende una sesión de coaching."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.training_service = TrainingService()

    @app_commands.command(name="agendar", description="Agenda una sesión de coaching")
    async def agendar(self, interaction: discord.Interaction) -> None:
        courses = await self.training_service.list_active_courses()
        if not courses:
            await interaction.response.send_message(
                "Todavía no hay cursos de coaching disponibles.", ephemeral=True
            )
            return

        if len(courses) == 1:
            # Un solo curso activo: nos ahorramos el primer paso de elegirlo.
            slots = await self.training_service.list_available_slots(courses[0].id)
            if not slots:
                await interaction.response.send_message(
                    "No hay horarios disponibles para ese curso por ahora.", ephemeral=True
                )
                return
            view = SlotSelectView(slots, self.training_service, interaction.user.id)
            await interaction.response.send_message("Elegí un horario:", view=view, ephemeral=True)
            return

        view = CourseSelectView(courses, self.training_service, interaction.user.id)
        await interaction.response.send_message("Elegí un curso:", view=view, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TrainingCog(bot))
