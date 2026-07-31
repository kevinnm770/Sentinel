from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext import commands

from config.settings import settings
from database.database import get_session
from database.repositories.session_repository import SessionRepository
from services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class SchedulerService:
    """Corre en segundo plano mientras el bot está vivo: cada un minuto
    revisa si hay sesiones para avisar o para cerrar.

    Usa APScheduler en vez de, por ejemplo, `asyncio.sleep` en un loop
    manual, porque ya resuelve cosas como no solapar dos ejecuciones del
    mismo job si una tarda más de un minuto, y loggear errores del job sin
    tirar abajo el proceso.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.notification_service = NotificationService(bot)
        self._scheduler = AsyncIOScheduler(timezone="UTC")

    def start(self) -> None:
        self._scheduler.add_job(
            self._check_upcoming_sessions, "interval", minutes=1, id="check_upcoming_sessions"
        )
        self._scheduler.add_job(
            self._close_finished_sessions, "interval", minutes=1, id="close_finished_sessions"
        )
        self._scheduler.start()
        logger.info("Scheduler iniciado (revisa sesiones cada 1 minuto)")

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    async def _check_upcoming_sessions(self) -> None:
        async with get_session() as session:
            repo = SessionRepository(session)
            upcoming = await repo.list_upcoming_unannounced(
                within_minutes=settings.announce_minutes_before
            )
            for session_row in upcoming:
                try:
                    await self.notification_service.announce_session(session_row)
                    await repo.mark_announced(session_row.id)
                except Exception:
                    logger.exception("Error al avisar la sesión %s", session_row.id)

    async def _close_finished_sessions(self) -> None:
        async with get_session() as session:
            repo = SessionRepository(session)
            finished = await repo.list_due_for_completion()
            for session_row in finished:
                try:
                    await self.notification_service.revoke_voice_access(session_row)
                    await repo.mark_completed(session_row.id)
                except Exception:
                    logger.exception("Error al cerrar la sesión %s", session_row.id)
