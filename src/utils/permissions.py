from __future__ import annotations

import discord

# Requisito de permiso por defecto para los grupos de comandos de
# administración. Discord usa esto para decidir a quién mostrarle el
# comando en el buscador (los dueños del servidor pueden reconfigurar esto
# manualmente en Integraciones, por eso además reforzamos con
# @app_commands.checks.has_permissions en cada comando).
ADMIN_ONLY = discord.Permissions(administrator=True)
