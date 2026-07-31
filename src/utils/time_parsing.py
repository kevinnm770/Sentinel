from __future__ import annotations

from datetime import date, time


def parse_date_ddmmyyyy(text: str) -> date:
    """Convierte un texto tipo '15/08/2026' a un `datetime.date`.

    Igual que con la hora, no hay un tipo de parámetro nativo de Discord
    para "fecha", así que la recibimos como texto libre y la validamos acá.
    """
    parts = text.strip().split("/")
    # El año tiene que tener 4 dígitos exactos: si no, "15/08/26" se
    # interpretaría en silencio como el año 26 (válido para Python, pero
    # casi seguro no es lo que quiso escribir quien lo tipeó).
    if (
        len(parts) != 3
        or not all(part.isdigit() for part in parts)
        or len(parts[2]) != 4
    ):
        raise ValueError(f"'{text}' no es una fecha válida. Usá el formato DD/MM/AAAA, ej. 15/08/2026.")

    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    try:
        return date(year=year, month=month, day=day)
    except ValueError:
        raise ValueError(f"'{text}' no es una fecha válida. Usá el formato DD/MM/AAAA, ej. 15/08/2026.") from None


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
