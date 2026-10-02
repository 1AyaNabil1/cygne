"""Tests for the scheduling service (database-only mode, no calendar/email)."""

from __future__ import annotations

import pytest

from cygne.config import get_settings
from cygne.db import session_scope
from cygne.db.models import Prospect
from cygne.scheduling import SchedulingService


def _service() -> SchedulingService:
    return SchedulingService(get_settings(), None)


@pytest.mark.asyncio
async def test_available_slots_are_future_weekdays() -> None:
    slots = await _service().available_slots()
    assert slots, "expected some open slots"
    assert all(s.weekday() < 5 for s in slots)
    assert all(s.hour in (10, 13, 16) for s in slots)


@pytest.mark.asyncio
async def test_booking_excludes_slot_and_requires_email(prospect_id: int) -> None:
    service = _service()
    slot = (await service.available_slots())[0]

    # No email yet -> refuses.
    refused = await service.book(prospect_id, slot.replace(tzinfo=None))
    assert "email" in refused.lower()

    async with session_scope() as session:
        prospect = await session.get(Prospect, prospect_id)
        prospect.email = "owner@shop.com"

    booked = await service.book(prospect_id, slot.replace(tzinfo=None))
    assert "Booked" in booked

    # The booked slot is no longer offered.
    assert slot not in await service.available_slots()
