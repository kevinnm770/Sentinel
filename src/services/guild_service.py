from __future__ import annotations

from database.database import get_session
from database.repositories.guild_settings_repository import GuildSettingsRepository


class GuildService:
    """Lógica de negocio para la configuración global del bot."""

    async def get_announcement_channel_id(self) -> int | None:
        async with get_session() as session:
            settings_row = await GuildSettingsRepository(session).get()
            return settings_row.announcement_channel_id

    async def set_announcement_channel(self, channel_id: int) -> None:
        async with get_session() as session:
            settings_row = await GuildSettingsRepository(session).get()
            settings_row.announcement_channel_id = channel_id
