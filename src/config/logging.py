from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from config.settings import PROJECT_ROOT, settings


def setup_logging() -> None:
    """Configura el logging de todo el bot. Se llama una sola vez, al arrancar.

    Escribe a dos destinos a la vez:
    - Consola, con formato coloreado (vía `rich`) para leer fácil en desarrollo.
    - Archivo en logs/, sin colores, para poder revisar el historial después
      (por ejemplo si el bot corre en un servidor sin que nadie mire la consola).
    """
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    root_logger.handlers.clear()

    console_handler = RichHandler(rich_tracebacks=True, show_path=False)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # RotatingFileHandler: cuando sentinel.log llega a 5MB, lo renombra a
    # sentinel.log.1 y empieza uno nuevo, conservando hasta 3 archivos viejos.
    # Sin esto, el log crecería indefinidamente mientras el bot esté prendido.
    file_handler = RotatingFileHandler(
        log_dir / "sentinel.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root_logger.addHandler(file_handler)

    # discord.py registra mucho detalle en nivel DEBUG (cada evento de la
    # conexión websocket); lo dejamos como mínimo en INFO para no inundar
    # los logs salvo que alguien esté depurando la librería en sí.
    discord_logger = logging.getLogger("discord")
    if discord_logger.level == logging.NOTSET or discord_logger.level < logging.INFO:
        discord_logger.setLevel(logging.INFO)
