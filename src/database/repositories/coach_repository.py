from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Coach


class CoachRepository:
    """Acceso a datos de Coach.

    Recibe la sesión desde afuera en vez de abrirla ella misma: quien la usa
    (el service) decide cuándo empieza y termina la transacción.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, *, discord_user_id: int, display_name: str, bio: str | None = None
    ) -> Coach:
        coach = Coach(discord_user_id=discord_user_id, display_name=display_name, bio=bio)
        self._session.add(coach)
        await self._session.flush()  # asigna el id sin cerrar la transacción todavía
        return coach

    async def get_by_discord_id(self, discord_user_id: int) -> Coach | None:
        result = await self._session.execute(
            select(Coach).where(Coach.discord_user_id == discord_user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_display_name(self, display_name: str) -> Coach | None:
        result = await self._session.execute(
            select(Coach).where(func.lower(Coach.display_name) == display_name.lower())
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Coach]:
        result = await self._session.execute(select(Coach).where(Coach.active.is_(True)))
        return list(result.scalars().all())
