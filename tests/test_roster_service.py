from __future__ import annotations

from datetime import time, timedelta

import pytest

from services.roster_service import (
    CoachNotFoundError,
    CourseNotFoundError,
    DuplicateCoachError,
    DuplicateCourseError,
    RecurringSlotNotFoundError,
    RosterService,
    SessionNotFoundError,
)
from utils.time_utils import utc_now


async def test_register_coach_creates_coach():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    assert coach.id is not None
    assert coach.display_name == "Coach A"


async def test_register_coach_rejects_duplicate_discord_user():
    roster = RosterService()
    await roster.register_coach(discord_user_id=1, display_name="Coach A")
    with pytest.raises(DuplicateCoachError):
        await roster.register_coach(discord_user_id=1, display_name="Otro nombre")


async def test_register_course_rejects_duplicate_name_case_insensitive():
    roster = RosterService()
    await roster.register_course(name="LoL Jungla")
    with pytest.raises(DuplicateCourseError):
        await roster.register_course(name="lol jungla")


async def test_list_active_coaches_returns_only_registered():
    roster = RosterService()
    assert await roster.list_active_coaches() == []
    await roster.register_coach(discord_user_id=1, display_name="Coach A")
    coaches = await roster.list_active_coaches()
    assert len(coaches) == 1
    assert coaches[0].display_name == "Coach A"


async def test_add_recurring_slot_rejects_invalid_day_of_week():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    with pytest.raises(ValueError):
        await roster.add_recurring_slot(
            coach_id=coach.id,
            course_id=course.id,
            day_of_week=7,  # solo 0-6 son válidos
            start_time=time(17, 0),
            duration_minutes=60,
        )


async def test_add_recurring_slot_rejects_non_positive_capacity():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    with pytest.raises(ValueError):
        await roster.add_recurring_slot(
            coach_id=coach.id,
            course_id=course.id,
            day_of_week=0,
            start_time=time(17, 0),
            duration_minutes=60,
            capacity=0,
        )


# --- editar / eliminar ---


async def test_edit_coach_updates_only_given_fields():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A", bio="bio original")
    updated = await roster.edit_coach(coach_id=coach.id, display_name="Coach B")
    assert updated.display_name == "Coach B"
    assert updated.bio == "bio original"  # no se tocó


async def test_edit_coach_missing_raises():
    roster = RosterService()
    with pytest.raises(CoachNotFoundError):
        await roster.edit_coach(coach_id=999, display_name="X")


async def test_deactivate_coach_removes_it_from_active_list():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    await roster.deactivate_coach(coach.id)
    assert await roster.list_active_coaches() == []


async def test_deactivate_coach_missing_raises():
    roster = RosterService()
    with pytest.raises(CoachNotFoundError):
        await roster.deactivate_coach(999)


async def test_reactivate_coach_via_edit():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    await roster.deactivate_coach(coach.id)
    await roster.edit_coach(coach_id=coach.id, active=True)
    coaches = await roster.list_active_coaches()
    assert len(coaches) == 1


async def test_edit_course_updates_only_given_fields():
    roster = RosterService()
    course = await roster.register_course(name="Curso A", game="LoL")
    updated = await roster.edit_course(course_id=course.id, name="Curso B")
    assert updated.name == "Curso B"
    assert updated.game == "LoL"


async def test_deactivate_course_missing_raises():
    roster = RosterService()
    with pytest.raises(CourseNotFoundError):
        await roster.deactivate_course(999)


async def test_edit_recurring_slot_updates_fields_and_rejects_invalid_day():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    slot = await roster.add_recurring_slot(
        coach_id=coach.id, course_id=course.id, day_of_week=0,
        start_time=time(17, 0), duration_minutes=60,
    )

    updated = await roster.edit_recurring_slot(slot_id=slot.id, capacity=5)
    assert updated.capacity == 5
    assert updated.day_of_week == 0  # no se tocó

    with pytest.raises(ValueError):
        await roster.edit_recurring_slot(slot_id=slot.id, day_of_week=9)


async def test_edit_recurring_slot_missing_raises():
    roster = RosterService()
    with pytest.raises(RecurringSlotNotFoundError):
        await roster.edit_recurring_slot(slot_id=999, capacity=2)


async def test_deactivate_recurring_slot_removes_it_from_active_list():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    slot = await roster.add_recurring_slot(
        coach_id=coach.id, course_id=course.id, day_of_week=0,
        start_time=time(17, 0), duration_minutes=60,
    )
    await roster.deactivate_recurring_slot(slot.id)
    assert await roster.list_active_recurring_slots() == []


# --- sesiones puntuales ---


async def test_create_standalone_session_requires_future_datetime():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    with pytest.raises(ValueError):
        await roster.create_standalone_session(
            coach_id=coach.id,
            course_id=course.id,
            scheduled_at=utc_now() - timedelta(days=1),
            duration_minutes=60,
        )


async def test_create_standalone_session_appears_in_upcoming_list():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    session_row = await roster.create_standalone_session(
        coach_id=coach.id,
        course_id=course.id,
        scheduled_at=utc_now() + timedelta(days=3),
        duration_minutes=60,
    )
    assert session_row.recurring_slot_id is None

    upcoming = await roster.list_upcoming_sessions()
    assert len(upcoming) == 1
    assert upcoming[0].id == session_row.id


async def test_cancel_session_removes_it_from_upcoming_list():
    roster = RosterService()
    coach = await roster.register_coach(discord_user_id=1, display_name="Coach A")
    course = await roster.register_course(name="Curso A")
    session_row = await roster.create_standalone_session(
        coach_id=coach.id,
        course_id=course.id,
        scheduled_at=utc_now() + timedelta(days=3),
        duration_minutes=60,
    )
    await roster.cancel_session(session_row.id)
    assert await roster.list_upcoming_sessions() == []


async def test_cancel_session_missing_raises():
    roster = RosterService()
    with pytest.raises(SessionNotFoundError):
        await roster.cancel_session(999)
