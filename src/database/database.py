from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import PROJECT_ROOT, settings


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos en models.py.

    SQLAlchemy usa esto para saber qué clases representan tablas y para
    generar el esquema (`Base.metadata`) que `init_db()` crea más abajo.
    """


def _resolve_database_url(url: str) -> str:
    """Ancla las rutas relativas de SQLite a la raíz del proyecto.

    Sin esto, `sqlite+aiosqlite:///data/sentinel.db` crearía el archivo en
    el directorio desde el que se ejecuta `python`, que cambia según desde
    dónde se corra el comando — un bug silencioso y confuso (el bot
    "pierde" sus datos porque en realidad está leyendo/escribiendo un
    archivo .db distinto cada vez).
    """
    prefix = "sqlite+aiosqlite:///"
    if url.startswith(prefix) and not url.startswith(prefix + "/"):
        relative_path = url.removeprefix(prefix)
        if not Path(relative_path).is_absolute():
            absolute_path = (PROJECT_ROOT / relative_path).resolve()
            return f"{prefix}{absolute_path.as_posix()}"
    return url


engine = create_async_engine(_resolve_database_url(settings.database_url))

# `expire_on_commit=False`: por defecto, SQLAlchemy invalida los objetos
# después de un commit (hay que releerlos de la BD para usarlos de nuevo).
# En un bot eso es incómodo porque solemos hacer commit y después seguir
# usando el objeto (ej. para armar el mensaje de confirmación en Discord).
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Entrega una sesión de base de datos y hace commit/rollback al salir.

    Uso típico dentro de un service:

        async with get_session() as session:
            session.add(nuevo_coach)
            # el commit ocurre solo, al salir del bloque `async with`
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Crea las tablas que falten según los modelos definidos en models.py.

    Sirve mientras el esquema todavía está tomando forma. Cuando lo
    estabilicemos vamos a introducir Alembic, que versiona los cambios de
    esquema sin borrar datos ya guardados (a diferencia de esto, que solo
    sabe crear tablas nuevas, no modificar las existentes).
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
