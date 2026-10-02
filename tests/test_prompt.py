"""Tests for the system prompt: what it tells the agent it knows and still needs."""

from __future__ import annotations

from cygne.agent.prompt import PromptContext, build_system_prompt


def test_a_new_prospect_has_everything_still_to_find_out() -> None:
    prompt = build_system_prompt(PromptContext(today="October 02, 2026", agency_name="Nile Media"))
    assert "enquiries for Nile Media" in prompt
    assert "- Nothing yet." in prompt
    assert (
        "Still to find out: What they want from us, Goals or problems, Monthly budget, "
        "Timeline, Decides" in prompt
    )
    assert "They have talked to us before" not in prompt


def test_known_details_are_listed_and_not_asked_again() -> None:
    prompt = build_system_prompt(
        PromptContext(
            today="October 02, 2026",
            company="Bloom Bakery",
            services=["Google Ads"],
            ad_budget="2000/month",
            decision_maker=True,
            qualification="medium",
            score=55,
        )
    )
    assert "- Company: Bloom Bakery" in prompt
    assert "- What they want from us: Google Ads" in prompt
    assert "- Decides: yes" in prompt
    assert "Lead standing: medium (55/100)." in prompt
    assert "Still to find out: Goals or problems, Timeline" in prompt


def test_a_returning_prospect_gets_the_notes() -> None:
    prompt = build_system_prompt(
        PromptContext(today="x", memory_summary="Business: bakery", is_returning=True)
    )
    assert "They have talked to us before\nBusiness: bakery" in prompt
