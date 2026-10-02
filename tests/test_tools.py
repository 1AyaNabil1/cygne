"""Tests for the agent tools against a real (SQLite) database."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from cygne.config import get_settings
from cygne.db import session_scope
from cygne.db.models import Appointment, Prospect, Quote, QuoteStatus
from cygne.scheduling import SchedulingService
from cygne.scheduling.service import slot_label
from cygne.tools.escalation import build_escalate_tool
from cygne.tools.lead_context import build_update_lead_context_tool
from cygne.tools.quote import build_draft_quote_tool
from cygne.tools.scheduling import build_schedule_meeting_tool


def _scheduling() -> SchedulingService:
    """Scheduling service with no calendar/email (DB-only) for tests."""
    return SchedulingService(get_settings(), None)


@pytest.mark.asyncio
async def test_update_lead_context_saves_and_scores(prospect_id: int) -> None:
    tool = build_update_lead_context_tool(prospect_id)
    result = await tool.ainvoke(
        {
            "industry": "ecommerce",
            "ad_budget": "$3000/month",
            "services": ["Meta ads"],
            "decision_maker": True,
        }
    )
    assert "Lead score is now" in result
    async with session_scope() as session:
        prospect = await session.get(Prospect, prospect_id)
        await session.refresh(prospect, ["lead"])
        # need 15 (one service) + budget 30 (3x the minimum) + authority 15
        assert prospect.lead.score == 60
        assert prospect.lead.industry == "ecommerce"
        assert prospect.lead.extra["score_breakdown"]["budget"] == 30

    # A second save merges lists instead of replacing them
    await tool.ainvoke({"services": ["Meta ads", "a landing page"]})
    async with session_scope() as session:
        prospect = await session.get(Prospect, prospect_id)
        await session.refresh(prospect, ["lead"])
        assert prospect.lead.extra["services"] == ["Meta ads", "a landing page"]


@pytest.mark.asyncio
async def test_draft_quote_is_pending_and_notifies(prospect_id: int) -> None:
    notified: list[tuple[int, int, str]] = []

    async def notifier(quote_id: int, pid: int, body: str) -> None:
        notified.append((quote_id, pid, body))

    tool = build_draft_quote_tool(prospect_id, notifier)
    await tool.ainvoke({"body": "Growth package: $3000/mo for ads + funnels."})

    assert len(notified) == 1
    async with session_scope() as session:
        quote = (await session.execute(select(Quote))).scalar_one()
        assert quote.status == QuoteStatus.PENDING
        assert notified[0][0] == quote.id


@pytest.mark.asyncio
async def test_schedule_requires_email(prospect_id: int) -> None:
    service = _scheduling()
    label = slot_label((await service.available_slots())[0])
    result = await build_schedule_meeting_tool(service, prospect_id).ainvoke({"slot": label})
    assert "email" in result.lower()


@pytest.mark.asyncio
async def test_schedule_books_with_email(prospect_id: int) -> None:
    async with session_scope() as session:
        prospect = await session.get(Prospect, prospect_id)
        prospect.email = "owner@shop.com"

    service = _scheduling()
    label = slot_label((await service.available_slots())[0])
    result = await build_schedule_meeting_tool(service, prospect_id).ainvoke({"slot": label})
    assert "Booked" in result
    async with session_scope() as session:
        appt = (await session.execute(select(Appointment))).scalar_one()
        assert appt.prospect_id == prospect_id


@pytest.mark.asyncio
async def test_schedule_rejects_unknown_slot(prospect_id: int) -> None:
    async with session_scope() as session:
        prospect = await session.get(Prospect, prospect_id)
        prospect.email = "owner@shop.com"
    tool = build_schedule_meeting_tool(_scheduling(), prospect_id)
    result = await tool.ainvoke({"slot": "Someday, Month 99 at 25:00"})
    assert "isn't on the list" in result.lower()


@pytest.mark.asyncio
async def test_escalation_notifies(prospect_id: int) -> None:
    seen: list[tuple[int, str]] = []

    async def notifier(pid: int, reason: str) -> None:
        seen.append((pid, reason))

    tool = build_escalate_tool(prospect_id, notifier)
    await tool.ainvoke({"reason": "prospect asked for a human"})
    assert seen == [(prospect_id, "prospect asked for a human")]
