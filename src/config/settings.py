from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raíz del proyecto (carpeta que contiene src/, data/, logs/, .env)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Configuración del bot, leída y validada desde variables de entorno (.env).

    pydantic-settings mapea cada variable de entorno a un campo de forma
    insensible a mayúsculas (DISCORD_TOKEN -> discord_token) y valida el tipo:
    si falta una variable obligatoria o tiene un valor inválido, el bot falla
    al arrancar con un mensaje claro, en vez de fallar más tarde de forma rara.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_token: str
    dev_guild_id: int | None = None
    timezone: str = "America/Bogota"
    database_url: str = "sqlite+aiosqlite:///data/sentinel.db"
    log_level: str = "INFO"
    # Con cuánta anticipación se avisa en el canal que una sesión está por
    # empezar (y se abre el acceso al canal de voz).
    announce_minutes_before: int = 10


# Instancia única, creada al importar este módulo. El resto del proyecto
# hace `from config.settings import settings` y reutiliza esta misma instancia.
settings = Settings()
