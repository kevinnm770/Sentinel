from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Course


class CourseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self, *, name: str, game: str | None = None, description: str | None = None
    ) -> Course:
        course = Course(name=name, game=game, description=description)
        self._session.add(course)
        await self._session.flush()
        return course

    async def get_by_name(self, name: str) -> Course | None:
        result = await self._session.execute(
            select(Course).where(func.lower(Course.name) == name.lower())
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Course]:
        result = await self._session.execute(select(Course).where(Course.active.is_(True)))
        return list(result.scalars().all())
