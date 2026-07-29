from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from services.guild_service import GuildService
from utils.permissions import ADMIN_ONLY


class SetupCog(commands.Cog):
    """Comandos de configuración inicial del bot. Requieren permiso de Administrador."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild_service = GuildService()

    setup_group = app_commands.Group(
        name="setup",
        description="Configuración general del bot",
        default_permissions=ADMIN_ONLY,
    )

    @setup_group.command(
        name="canal-avisos", description="Define en qué canal se anuncian los coachings"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(canal="Canal de texto donde se van a publicar los avisos")
    async def canal_avisos(
        self, interaction: discord.Interaction, canal: discord.TextChannel
    ) -> None:
        await self.guild_service.set_announcement_channel(canal.id)
        await interaction.response.send_message(
            f"Listo, los avisos de coaching se van a publicar en {canal.mention}.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SetupCog(bot))
