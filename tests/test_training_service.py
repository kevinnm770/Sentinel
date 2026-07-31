from __future__ import annotations

from datetime import time

import pytest

from database.database import get_session
from database.models import RecurringSlot
from database.repositories.session_repository import SessionRepository
from services.roster_service import RosterService
from services.training_service import (
    AlreadyEnrolledError,
    EnrollmentNotFoundError,
    SlotFullError,
    SlotNotFoundError,
    TrainingService,
)


async def _make_slot(capacity: int = 1) -> RecurringSlot:
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    return await roster.add_recurring_slot(
        coach_id=coach.id,
        course_id=course.id,
        day_of_week=0,
        start_time=time(17, 0),
        duration_minutes=60,
        capacity=capacity,
    )


async def _session_id_for(slot: RecurringSlot, scheduled_at) -> int:
    async with get_session() as session:
        session_row = await SessionRepository(session).get_by_slot_and_time(slot.id, scheduled_at)
        return session_row.id


async def test_book_creates_enrollment_and_uses_up_capacity():
    slot = await _make_slot(capacity=1)
    training = TrainingService()
    booked = await training.book(recurring_slot_id=slot.id, student_discord_id=100)
    assert booked.spots_left == 0


async def test_book_same_student_twice_raises():
    slot = await _make_slot(capacity=2)
    training = TrainingService()
    await training.book(recurring_slot_id=slot.id, student_discord_id=100)
    with pytest.raises(AlreadyEnrolledError):
        await training.book(recurring_slot_id=slot.id, student_discord_id=100)


async def test_book_beyond_capacity_raises():
    slot = await _make_slot(capacity=1)
    training = TrainingService()
    await training.book(recurring_slot_id=slot.id, student_discord_id=100)
    with pytest.raises(SlotFullError):
        await training.book(recurring_slot_id=slot.id, student_discord_id=200)


async def test_full_slot_is_excluded_from_available_list():
    slot = await _make_slot(capacity=1)
    training = TrainingService()
    course_id = slot.course_id
    available_before = await training.list_available_slots(course_id)
    assert len(available_before) == 1

    await training.book(recurring_slot_id=slot.id, student_discord_id=100)

    available_after = await training.list_available_slots(course_id)
    assert available_after == []


async def test_cancel_then_rebook_same_student_works():
    slot = await _make_slot(capacity=1)
    training = TrainingService()
    booked = await training.book(recurring_slot_id=slot.id, student_discord_id=100)
    session_id = await _session_id_for(slot, booked.next_occurrence)

    await training.cancel_enrollment(session_id=session_id, student_discord_id=100)
    # El mismo estudiante debería poder volver a anotarse sin chocar con el
    # UniqueConstraint de la fila que canceló antes (se reactiva esa fila).
    rebooked = await training.book(recurring_slot_id=slot.id, student_discord_id=100)
    assert rebooked.spots_left == 0


async def test_cancel_without_being_enrolled_raises():
    slot = await _make_slot(capacity=1)
    training = TrainingService()
    booked = await training.book(recurring_slot_id=slot.id, student_discord_id=100)
    session_id = await _session_id_for(slot, booked.next_occurrence)

    with pytest.raises(EnrollmentNotFoundError):
        await training.cancel_enrollment(session_id=session_id, student_discord_id=999)


async def test_cancel_frees_up_spot_for_another_student():
    slot = await _make_slot(capacity=1)
    training = TrainingService()
    booked = await training.book(recurring_slot_id=slot.id, student_discord_id=100)
    session_id = await _session_id_for(slot, booked.next_occurrence)

    await training.cancel_enrollment(session_id=session_id, student_discord_id=100)
    # Ahora otra persona debería poder tomar el cupo liberado.
    booked_other = await training.book(recurring_slot_id=slot.id, student_discord_id=200)
    assert booked_other.spots_left == 0


async def test_deactivated_coach_hides_slot_from_availability():
    roster = RosterService()
    slot = await _make_slot(capacity=1)
    await roster.deactivate_coach(slot.coach_id)

    training = TrainingService()
    assert await training.list_available_slots(slot.course_id) == []
    with pytest.raises(SlotNotFoundError):
        await training.book(recurring_slot_id=slot.id, student_discord_id=100)


async def test_deactivated_course_hides_slot_from_availability():
    roster = RosterService()
    slot = await _make_slot(capacity=1)
    await roster.deactivate_course(slot.course_id)

    training = TrainingService()
    assert await training.list_available_slots(slot.course_id) == []
    with pytest.raises(SlotNotFoundError):
        await training.book(recurring_slot_id=slot.id, student_discord_id=100)
