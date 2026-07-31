from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Estas variables tienen que quedar seteadas ANTES de que cualquier test
# importe algo de `config`/`database` (Settings() las lee una sola vez, al
# importarse el módulo). Por eso viven acá arriba de todo en conftest.py:
# pytest garantiza que este archivo se carga antes que los test_*.py.
_temp_db_fd, _temp_db_path = tempfile.mkstemp(suffix=".db", prefix="sentinel_test_")
os.close(_temp_db_fd)

os.environ["DISCORD_TOKEN"] = "test-token"
os.environ["TIMEZONE"] = "America/Bogota"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{Path(_temp_db_path).as_posix()}"

import pytest  # noqa: E402

from database.database import Base, engine  # noqa: E402
from database import models  # noqa: E402,F401  (registra las tablas contra Base.metadata)


@pytest.fixture(autouse=True)
async def _clean_database():
    """Antes de cada test, recrea el esquema desde cero: cada test arranca
    con una base de datos vacía, sin datos que dejaron tests anteriores."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


def pytest_sessionfinish(session, exitstatus) -> None:
    import asyncio

    # En Windows no se puede borrar un archivo mientras sigue abierto: hay
    # que cerrar las conexiones del pool del engine antes de intentarlo.
    asyncio.run(engine.dispose())
    Path(_temp_db_path).unlink(missing_ok=True)
