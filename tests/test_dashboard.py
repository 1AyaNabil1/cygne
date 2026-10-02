"""Tests for the read-only dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from cygne.config import get_settings
from cygne.dashboard.app import app
from cygne.dashboard.data import load_dashboard
from cygne.db import session_scope
from cygne.db.helpers import create_appointment, get_or_create_prospect, save_lead_context
from cygne.leads import score_lead


async def _seed() -> None:
    async with session_scope() as session:
        prospect = await get_or_create_prospect(session, "telegram", "dash-1")
        prospect.company = "GlowShop"
        prospect.email = "owner@glowshop.com"
        await save_lead_context(
            session,
            prospect.lead,
            {"industry": "ecommerce", "ad_budget": "$3000", "business_stage": "scaling"},
        )
        score_lead(prospect.lead)
        await create_appointment(
            session, prospect.id, datetime.now() + timedelta(days=2), notes="call"
        )


@pytest.mark.asyncio
async def test_load_dashboard_counts() -> None:
    await _seed()
    data = await load_dashboard()
    assert data.total_leads == 1
    assert data.qualified_leads == 1
    assert data.meetings_booked == 1
    assert data.leads[0].company == "GlowShop"


@pytest.fixture
def password(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(get_settings(), "dashboard_password", "s3cret")
    return "s3cret"


@pytest.mark.asyncio
async def test_dashboard_page_renders_for_the_operator(password: str) -> None:
    await _seed()
    with TestClient(app) as client:
        response = client.get("/", auth=("operator", password))
    assert response.status_code == 200
    assert "GlowShop" in response.text
    assert "Lead Pipeline" in response.text
    # Why the lead scored what it did: budget 3x the minimum, email and company known
    assert "budget 30" in response.text
    assert "reachability 10" in response.text


@pytest.mark.asyncio
async def test_dashboard_needs_the_password(password: str) -> None:
    with TestClient(app) as client:
        assert client.get("/").status_code == 401
        assert client.get("/", auth=("operator", "wrong")).status_code == 401
        assert client.get("/", auth=("admin", password)).status_code == 401
        assert client.get("/health").status_code == 200


@pytest.mark.asyncio
async def test_dashboard_stays_closed_until_a_password_is_set(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "dashboard_password", "")
    with TestClient(app) as client:
        response = client.get("/", auth=("operator", ""))
    assert response.status_code == 503
    assert "CYGNE_DASHBOARD_PASSWORD" in response.text
