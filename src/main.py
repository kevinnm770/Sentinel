from __future__ import annotations

import asyncio
import logging

from bot import SentinelBot
from config.logging import setup_logging
from config.settings import settings
from database.database import init_db

# Import necesario aunque no se use directamente: al importarse, registra
# todas las clases de modelos contra Base.metadata. Sin esto, init_db()
# no "conocería" ninguna tabla y create_all() no crearía nada.
from database import models  # noqa: F401

logger = logging.getLogger(__name__)


async def main() -> None:
    setup_logging()
    await init_db()
    bot = SentinelBot()
    async with bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    asyncio.run(main())
