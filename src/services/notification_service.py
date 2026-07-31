from __future__ import annotations

import logging

import discord
from discord.ext import commands

from database.models import Enrollment, EnrollmentStatus, Session
from services.guild_service import GuildService
from utils.time_utils import to_local
from utils.weekdays import DAY_NAMES

logger = logging.getLogger(__name__)


class NotificationService:
    """Avisa en Discord cuando una sesión está por empezar y administra el
    acceso al canal de voz asignado (si tiene uno).

    Necesita una referencia al bot (no a un servicio) porque, a diferencia
    de guild_service o roster_service, esto no es una operación de base de
    datos: es mandar mensajes y tocar permisos de canales reales de Discord.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild_service = GuildService()

    async def announce_session(self, session_row: Session) -> None:
        confirmed = [e for e in session_row.enrollments if e.status == EnrollmentStatus.CONFIRMED]
        if not confirmed:
            # Puede pasar si todos los anotados cancelaron después de que
            # se generó la sesión. No hay a quién avisar.
            return

        channel_id = await self.guild_service.get_announcement_channel_id()
        if channel_id is None:
            logger.warning(
                "No hay canal de avisos configurado (/setup canal-avisos); "
                "no se pudo avisar la sesión %s",
                session_row.id,
            )
            return

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("El canal de avisos %s ya no existe o no es de texto", channel_id)
            return

        local_time = to_local(session_row.scheduled_at)
        fecha_texto = f"{DAY_NAMES[local_time.weekday()]} {local_time.strftime('%H:%M')}"
        mentions = " ".join(f"<@{e.student_discord_id}>" for e in confirmed)
        voice_text = (
            f"\nConectate en <#{session_row.voice_channel_id}>." if session_row.voice_channel_id else ""
        )

        await channel.send(
            f"📢 **{session_row.course.name}** con **{session_row.coach.display_name}** "
            f"empieza a las {fecha_texto}. {mentions}{voice_text}"
        )

        if session_row.voice_channel_id:
            await self._grant_voice_access(session_row, confirmed)

    async def _grant_voice_access(self, session_row: Session, confirmed: list[Enrollment]) -> None:
        voice_channel = self.bot.get_channel(session_row.voice_channel_id)
        if not isinstance(voice_channel, discord.VoiceChannel):
            logger.warning(
                "El canal de voz %s de la sesión %s ya no existe o no es de voz",
                session_row.voice_channel_id,
                session_row.id,
            )
            return

        guild = voice_channel.guild
        try:
            # Cerramos el canal para todos por defecto...
            await voice_channel.set_permissions(
                guild.default_role,
                connect=False,
                reason=f"Sesión de coaching #{session_row.id}: canal restringido",
            )
            # ...y lo abrimos solo para el coach y los estudiantes anotados.
            member_ids = {session_row.coach.discord_user_id, *(e.student_discord_id for e in confirmed)}
            for discord_user_id in member_ids:
                member = await self._safe_fetch_member(guild, discord_user_id)
                if member is not None:
                    await voice_channel.set_permissions(
                        member, connect=True, reason=f"Participante de la sesión #{session_row.id}"
                    )
        except discord.Forbidden:
            logger.warning(
                "Al bot le falta el permiso 'Gestionar canales' en %s para restringir el acceso "
                "de voz de la sesión %s",
                voice_channel.name,
                session_row.id,
            )

    async def revoke_voice_access(self, session_row: Session) -> None:
        if not session_row.voice_channel_id:
            return
        voice_channel = self.bot.get_channel(session_row.voice_channel_id)
        if not isinstance(voice_channel, discord.VoiceChannel):
            return

        guild = voice_channel.guild
        try:
            # Sacamos los permisos puntuales que le dimos a coach/estudiantes
            # y reabrimos el canal, para que la próxima ocurrencia (con
            # otros estudiantes, si es 1 a 1) arranque de cero.
            for target, _overwrite in list(voice_channel.overwrites.items()):
                if isinstance(target, discord.Member):
                    await voice_channel.set_permissions(
                        target, overwrite=None, reason=f"Fin de la sesión #{session_row.id}"
                    )
            await voice_channel.set_permissions(
                guild.default_role, overwrite=None, reason=f"Fin de la sesión #{session_row.id}"
            )
        except discord.Forbidden:
            logger.warning(
                "Al bot le falta el permiso 'Gestionar canales' en %s para liberar el acceso "
                "de voz de la sesión %s",
                voice_channel.name,
                session_row.id,
            )

    @staticmethod
    async def _safe_fetch_member(guild: discord.Guild, discord_user_id: int) -> discord.Member | None:
        # `fetch_member` pega contra la API en vez de depender del caché de
        # miembros, así evitamos tener que pedir el intent privilegiado de
        # "Server Members" solo para esto.
        try:
            return await guild.fetch_member(discord_user_id)
        except discord.NotFound:
            return None
