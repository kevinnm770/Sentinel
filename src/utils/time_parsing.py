from __future__ import annotations

from datetime import time


def parse_time_hhmm(text: str) -> time:
    """Convierte un texto tipo '17:00' o '9:30' a un `datetime.time`.

    Los slash commands de Discord no tienen un tipo de parámetro nativo para
    "hora del día", así que lo recibimos como texto libre y lo validamos acá.
    Lanza ValueError con un mensaje pensado para mostrarle directo al
    usuario si el formato no es válido.
    """
    parts = text.strip().split(":")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError(f"'{text}' no es una hora válida. Usá el formato HH:MM, ej. 17:00.")

    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"'{text}' no es una hora válida. La hora debe ser 00-23 y los minutos 00-59.")

    return time(hour=hour, minute=minute)
