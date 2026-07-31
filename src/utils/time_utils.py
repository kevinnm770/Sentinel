from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from config.settings import settings


def utc_now() -> datetime:
    """'Ahora' en UTC, sin tzinfo (naive).

    Toda la base de datos guarda datetimes naive-pero-UTC porque SQLite no
    conserva el offset de zona horaria al guardar (lo comprobamos: un
    datetime con tzinfo se graba y, al releerlo, vuelve sin tzinfo). Si
    mezcláramos datetimes 'aware' y 'naive' en una comparación, Python
    tira TypeError. Esta función existe para que 'ahora' se genere siempre
    en el mismo formato que lo que sale de la base de datos.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_local(utc_naive: datetime) -> datetime:
    """Convierte un datetime naive-UTC (como vienen de la base de datos) a
    la zona horaria configurada del servidor, para mostrárselo al usuario."""
    return utc_naive.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(settings.timezone))


def combine_local_to_utc(local_date: date, local_time: time) -> datetime:
    """Combina una fecha y hora dadas en la zona horaria del servidor y las
    convierte a UTC naive (la convención de toda la base de datos). Sirve
    para cuando un admin ingresa una fecha/hora exacta a mano."""
    local_dt = datetime.combine(local_date, local_time, tzinfo=ZoneInfo(settings.timezone))
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)
