"""Tests for the explainable lead score, budget parsing and de-duplication."""

from __future__ import annotations

import pytest

from cygne.db.models import LeadContext, Prospect, QualificationStatus
from cygne.leads import parse_budget, score_breakdown, score_lead
from cygne.leads.dedup import deduplicate
from cygne.leads.scoring import timeline_strength


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$3,000/mo", 3000.0),
        ("around 2500 per month", 2500.0),
        ("2.5k", 2500.0),
        ("5K a month", 5000.0),
        ("", None),
        (None, None),
        ("not sure yet", None),
    ],
)
def test_parse_budget(raw: str | None, expected: float | None) -> None:
    assert parse_budget(raw) == expected


@pytest.mark.parametrize(
    ("timeline", "strength"),
    [
        ("ASAP", 1.0),
        ("this month", 1.0),
        ("in 2 months", 0.7),
        ("next quarter", 0.25),
        ("just exploring", 0.25),
        ("after Ramadan", 0.5),
        (None, 0.0),
    ],
)
def test_timeline_strength(timeline: str | None, strength: float) -> None:
    assert timeline_strength(timeline) == strength


def test_a_ready_lead_scores_full_marks() -> None:
    lead = LeadContext(
        prospect=Prospect(email="a@b.com", company="Acme"),
        ad_budget="5000/month",
        timeline="as soon as possible",
        extra={"services": ["Google Ads"], "challenges": ["more bookings"], "decision_maker": True},
    )
    assert score_lead(lead, minimum_budget=1000) == 100
    assert lead.qualification == QualificationStatus.HIGH
    assert lead.extra["score_breakdown"] == {
        "need": 25,
        "budget": 30,
        "timeline": 20,
        "authority": 15,
        "reachability": 10,
    }


def test_partial_information_earns_partial_points() -> None:
    lead = LeadContext(
        prospect=Prospect(email="a@b.com"),
        ad_budget="800",  # below a 1000 minimum
        extra={"services": ["SEO"], "decision_maker": False},
    )
    assert score_breakdown(lead, minimum_budget=1000) == {
        "need": 15,
        "budget": 12,
        "timeline": 0,
        "authority": 4,
        "reachability": 6,
    }
    assert score_lead(lead, minimum_budget=1000) == 37
    assert lead.qualification == QualificationStatus.LOW


def test_budget_is_judged_against_the_agency_minimum() -> None:
    lead = LeadContext(prospect=Prospect(), ad_budget="3000")
    assert score_breakdown(lead, minimum_budget=1000)["budget"] == 30
    assert score_breakdown(lead, minimum_budget=5000)["budget"] == 12


def test_empty_lead_is_unqualified_and_scoring_keeps_other_context() -> None:
    lead = LeadContext(prospect=Prospect(), extra={"phone": "123"})
    assert score_lead(lead) == 0
    assert lead.qualification == QualificationStatus.UNQUALIFIED
    assert lead.extra["phone"] == "123"


def test_deduplicate_keeps_the_most_specific_phrase() -> None:
    items = ["need more leads", "More leads needed!", "SEO", "better SEO", "ads", "Facebook ads"]
    assert deduplicate(items) == ["need more leads", "better SEO", "Facebook ads"]


def test_deduplicate_keeps_unrelated_and_drops_blank() -> None:
    assert deduplicate(["ads", "a new website", "  "]) == ["ads", "a new website"]
