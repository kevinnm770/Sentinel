# Sentinel

Bot de Discord para gestionar coaching de videojuegos: agendamiento de sesiones 1 a 1 o grupales, horarios recurrentes, avisos automáticos cuando una sesión está por empezar y un canal de voz que se restringe solo a los participantes.

## Funcionalidad

- **Panel de administración** (comandos slash, solo Administrador): registrar coaches, cursos y horarios recurrentes semanales, con canal de voz opcional asignado.
- **Agendamiento** (`/agendar`): cualquier usuario elige curso y horario disponible desde un menú interactivo, y queda anotado.
- **Recurrencia**: un horario "todos los lunes 17hs" genera automáticamente la sesión concreta de cada semana la primera vez que alguien la agenda.
- **Avisos automáticos**: minutos antes de que empiece una sesión, el bot publica un aviso en el canal configurado mencionando a los anotados, y abre el canal de voz asignado solo para el coach y esos estudiantes (se vuelve a cerrar al terminar).
- **Gestión personal** (`/mis-coachings`, `/cancelar-coaching`): cada usuario ve y cancela sus propias sesiones agendadas.

## Stack

- **discord.py** — slash commands, componentes interactivos (menús), eventos.
- **SQLAlchemy 2.0 (async) + aiosqlite** — capa de datos, SQLite por defecto.
- **Alembic** — migraciones de esquema.
- **APScheduler** — chequeos periódicos en segundo plano (avisos, cierre de sesiones).
- **pydantic-settings** — configuración validada desde `.env`.
- **pytest + pytest-asyncio** — tests.

## Estructura

```
src/
├── bot.py              # Clase del bot: carga cogs, sincroniza comandos, ciclo de vida
├── main.py              # Punto de entrada
├── config/               # Configuración (.env) y logging
├── cogs/                 # Comandos de Discord, agrupados por área
├── ui/                    # Componentes interactivos (menús de agendamiento)
├── services/             # Lógica de negocio, independiente de Discord
├── database/
│   ├── models.py          # Tablas
│   ├── database.py        # Motor de conexión y sesiones
│   └── repositories/      # Acceso a datos, un repositorio por modelo
└── utils/                # Helpers compartidos (fechas, permisos, parsing)
alembic/                  # Migraciones de base de datos
tests/                     # Tests (pytest)
```

## Configuración inicial

### 1. Crear la aplicación en Discord

En el [Developer Portal](https://discord.com/developers/applications), creá una aplicación y un bot. Necesitás:

- El **token** del bot (Bot > Reset Token).
- Invitarlo a tu servidor con los scopes `bot` y `applications.commands`, y estos permisos:
  - `Send Messages`
  - `Manage Channels` (necesario para restringir el canal de voz a los participantes de cada sesión — sin este permiso, el bot va a avisar la sesión igual pero no va a poder abrir/cerrar el acceso al canal de voz)

No hace falta activar ningún intent privilegiado (contenido de mensajes, miembros): el bot los evita a propósito para no requerir esa aprobación extra.

### 2. Variables de entorno

Copiá `.env.example` a `.env` y completá:

| Variable | Descripción |
|---|---|
| `DISCORD_TOKEN` | Token del bot. Nunca lo compartas ni lo subas a git. |
| `DEV_GUILD_ID` | ID de tu servidor de pruebas (sincroniza comandos al instante ahí en vez de esperar hasta 1h). |
| `TIMEZONE` | Zona horaria única del servidor (ej. `America/Bogota`). |
| `DATABASE_URL` | Ruta a la base SQLite. Por defecto `data/sentinel.db`. |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` o `ERROR`. |
| `ANNOUNCE_MINUTES_BEFORE` | Con cuánta anticipación se avisa que una sesión empieza. |

### 3. Instalar y correr

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py
```

La primera vez, esto crea automáticamente `data/sentinel.db` con todas las tablas.

## Base de datos y migraciones

El esquema se gestiona con Alembic. Si en el futuro se modifica `src/database/models.py`:

```powershell
# Generar una migración a partir de los cambios en los modelos
alembic revision --autogenerate -m "descripción del cambio"

# Revisar el archivo generado en alembic/versions/ antes de aplicarlo

# Aplicarla
alembic upgrade head
```

## Tests

```powershell
pytest
```

Los tests corren contra una base de datos SQLite temporal (no tocan `data/sentinel.db`) que se recrea antes de cada test.

## Comandos

**Administración** (requieren permiso de Administrador del servidor):
- `/setup canal-avisos` — define el canal donde se publican los avisos de sesión.
- `/coach agregar` / `listar` / `editar` / `eliminar`
- `/curso agregar` / `listar` / `editar` / `eliminar`
- `/horario agregar` / `listar` / `editar` / `eliminar` — horarios recurrentes semanales, con cupo y canal de voz opcionales.
- `/sesion agregar` / `listar` / `eliminar` — sesiones puntuales con fecha exacta (`DD/MM/AAAA`), sin necesidad de un horario recurrente detrás.

`eliminar` es siempre un borrado lógico (desactiva el registro, no lo borra de la base): un coach o curso desactivado deja de ofrecerse para agendar, pero se puede reactivar con `editar activo:True`. Esto también aplica en cascada a sus horarios: si desactivás un coach, sus horarios dejan de aparecer como agendables aunque el horario en sí siga activo.

**Para cualquier usuario:**
- `/agendar` — agenda una sesión de coaching.
- `/mis-coachings` — lista tus sesiones agendadas.
- `/cancelar-coaching` — cancela una sesión agendada.
- `/ping` — verifica que el bot esté activo.
