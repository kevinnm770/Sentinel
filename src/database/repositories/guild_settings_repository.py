from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import GuildSettings


class GuildSettingsRepository:
    """La configuración global vive en una única fila (id=1). Este
    repositorio la crea la primera vez que se necesita (patrón get-or-create)
    en vez de requerir un paso de inicialización aparte.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self) -> GuildSettings:
        settings_row = await self._session.get(GuildSettings, 1)
        if settings_row is None:
            settings_row = GuildSettings(id=1)
            self._session.add(settings_row)
            await self._session.flush()
        return settings_row
