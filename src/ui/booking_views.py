from __future__ import annotations

import discord

from database.models import Course
from services.training_service import (
    AlreadyEnrolledError,
    SlotAvailability,
    SlotFullError,
    SlotNotFoundError,
    TrainingService,
)
from utils.time_utils import to_local
from utils.weekdays import DAY_NAMES


class SlotSelectView(discord.ui.View):
    """Segundo paso: elegir uno de los horarios disponibles y agendarlo.

    El mensaje que contiene esta vista siempre se envía como ephemeral
    (solo lo ve quien ejecutó el comando), así que no hace falta validar
    que quien interactúa con el menú sea el mismo usuario que lo abrió.
    """

    def __init__(
        self, slots: list[SlotAvailability], training_service: TrainingService, student_id: int
    ) -> None:
        super().__init__(timeout=180)
        self.training_service = training_service
        self.student_id = student_id
        self.slot_select.options = [
            discord.SelectOption(
                label=f"{DAY_NAMES[slot.day_of_week]} {slot.start_time.strftime('%H:%M')} - {slot.coach_name}",
                description=f"{slot.course_name} · {slot.spots_left}/{slot.capacity} cupos libres",
                value=str(slot.recurring_slot_id),
            )
            for slot in slots
        ]

    @discord.ui.select(placeholder="Elegí un horario")
    async def slot_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        recurring_slot_id = int(select.values[0])
        try:
            booked = await self.training_service.book(
                recurring_slot_id=recurring_slot_id, student_discord_id=self.student_id
            )
        except (AlreadyEnrolledError, SlotFullError, SlotNotFoundError) as error:
            await interaction.response.edit_message(content=str(error), view=None)
            return

        local_time = to_local(booked.next_occurrence)
        fecha_texto = (
            f"{DAY_NAMES[local_time.weekday()]} {local_time.day:02d}/{local_time.month:02d} "
            f"a las {local_time.strftime('%H:%M')}"
        )
        await interaction.response.edit_message(
            content=(
                f"¡Listo! Quedaste anotado a **{booked.course_name}** con **{booked.coach_name}** "
                f"el {fecha_texto}."
            ),
            view=None,
        )


class CourseSelectView(discord.ui.View):
    """Primer paso: elegir un curso. Al seleccionar, reemplaza el mensaje
    con el segundo paso (los horarios disponibles de ese curso)."""

    def __init__(
        self, courses: list[Course], training_service: TrainingService, student_id: int
    ) -> None:
        super().__init__(timeout=180)
        self.training_service = training_service
        self.student_id = student_id
        self.course_select.options = [
            discord.SelectOption(label=course.name, description=course.game, value=str(course.id))
            for course in courses
        ]

    @discord.ui.select(placeholder="Elegí un curso")
    async def course_select(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ) -> None:
        course_id = int(select.values[0])
        slots = await self.training_service.list_available_slots(course_id)
        if not slots:
            await interaction.response.edit_message(
                content="No hay horarios disponibles para ese curso por ahora.", view=None
            )
            return
        view = SlotSelectView(slots, self.training_service, self.student_id)
        await interaction.response.edit_message(content="Elegí un horario:", view=view)
