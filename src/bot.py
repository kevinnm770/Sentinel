from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config.settings import settings

logger = logging.getLogger(__name__)

# Cogs que se cargan al arrancar. Cada entrada es "carpeta.archivo" dentro
# de src/. Para agregar un cog nuevo más adelante, solo hay que sumarlo acá.
EXTENSIONS = [
    "cogs.setup",
    "cogs.roster",
]


class SentinelBot(commands.Bot):
    """Bot principal de Sentinel.

    Subclase de `commands.Bot` (de discord.py) para engancharse a su ciclo de
    vida: `setup_hook()` corre una sola vez, después de autenticarse pero
    antes de empezar a recibir eventos, y es el lugar recomendado para cargar
    cogs y sincronizar los slash commands con Discord.
    """

    def __init__(self) -> None:
        # "Intents" son las categorías de eventos que Discord le permite
        # recibir al bot (mensajes, miembros que entran/salen, reacciones...).
        # Existen para privacidad y performance: un bot solo recibe lo que
        # explícitamente pide. `default()` alcanza para slash commands e
        # interacciones normales; no activamos los intents "privilegiados"
        # (contenido de mensajes, lista de miembros) porque no los usamos y
        # requieren habilitarlos a mano en el Developer Portal.
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        # Comando de salud, útil para confirmar rápido que el bot está vivo
        # y respondiendo, más allá de los cogs con la funcionalidad real.
        @self.tree.command(name="ping", description="Verifica que Sentinel esté activo")
        async def ping(interaction: discord.Interaction) -> None:
            latency_ms = round(self.latency * 1000)
            await interaction.response.send_message(f"🏓 Pong! ({latency_ms}ms)")

        for extension in EXTENSIONS:
            await self.load_extension(extension)
            logger.info("Cog cargado: %s", extension)

        self.tree.error(self._on_app_command_error)

        if settings.dev_guild_id:
            # Sincronizar los comandos a un único servidor es instantáneo,
            # ideal mientras desarrollamos. `copy_global_to` copia los
            # comandos definidos arriba a ese servidor específico.
            guild = discord.Object(id=settings.dev_guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info(
                "Sincronizados %d comando(s) en el servidor de desarrollo (%s)",
                len(synced),
                settings.dev_guild_id,
            )
        else:
            # Sin DEV_GUILD_ID, sincroniza globalmente: tarda hasta 1 hora en
            # propagarse a todos los servidores donde está el bot.
            synced = await self.tree.sync()
            logger.info("Sincronizados %d comando(s) globalmente", len(synced))

    async def on_ready(self) -> None:
        user = self.user
        logger.info("Conectado como %s (ID: %s)", user, user.id if user else "desconocido")

    @staticmethod
    async def _on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        # Manejador centralizado para errores de slash commands. Sin esto,
        # discord.py solo loguea el error y el usuario ve "La aplicación no
        # respondió" sin ninguna explicación.
        if isinstance(error, app_commands.MissingPermissions):
            message = "No tenés permiso para usar este comando."
        else:
            logger.exception("Error no manejado en un comando", exc_info=error)
            message = "Ocurrió un error inesperado. Ya quedó registrado en los logs."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
