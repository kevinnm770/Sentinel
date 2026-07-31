from __future__ import annotations

# 0 = lunes ... 6 = domingo (misma convención que datetime.weekday() de Python)
DAY_NAMES: dict[int, str] = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}
DAY_NUMBERS: dict[str, int] = {name: number for number, name in DAY_NAMES.items()}
