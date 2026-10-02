"""Tests for evidence-grounded lead extraction: a fact survives only if the prospect's
own words support it."""

from __future__ import annotations

import pytest

from cygne.leads import LeadFacts, LeadInfoExtractor

MESSAGES = [
    "Hi, I run Bloom Bakery in Alexandria, we sell cakes online.",
    "Honestly I want more orders from Instagram and maybe Google Ads.",
    "We can spend around 2k a month. I'm the owner so it's my call.",
    "My email is sara@bloombakery.com, we'd like to start next month.",
]
SOURCE = "\n".join(MESSAGES)


def q(value, quote):
    return {"value": value, "quote": quote}


class StubModel:
    """Stands in for a chat model's structured output."""

    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    def with_structured_output(self, schema, method):
        assert schema is LeadFacts and method == "function_calling"
        return self

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def verify(**facts):
    return LeadInfoExtractor(model=None).verify(LeadFacts(**facts), SOURCE)


def test_grounded_facts_are_kept() -> None:
    result = verify(
        company=q("Bloom Bakery", "I run Bloom Bakery in Alexandria"),
        email=q("sara@bloombakery.com", "My email is sara@bloombakery.com"),
        industry=q("online cake bakery", "we sell cakes online"),
        monthly_budget=q(2000, "We can spend around 2k a month"),
        timeline=q("next month", "we'd like to start next month"),
        decision_maker=q(True, "I'm the owner so it's my call"),
        services=[q("Google Ads", "maybe Google Ads")],
        goals=[q("more orders from Instagram", "I want more orders from Instagram")],
    )
    assert result.rejected == []
    assert result.contact == {"company": "Bloom Bakery", "email": "sara@bloombakery.com"}
    assert result.lead == {
        "industry": "online cake bakery",
        "timeline": "next month",
        "decision_maker": True,
        "ad_budget": "2000/month",
        "services": ["Google Ads"],
        "challenges": ["more orders from Instagram"],
    }


def test_a_fact_without_the_prospects_words_is_dropped() -> None:
    result = verify(
        industry=q("bakery", "we sell cakes online"),
        timeline=q("this week", "we want to start this week"),  # never said
        goals=[q("brand awareness", "build our brand awareness")],  # never said
    )
    assert result.lead == {"industry": "bakery"}
    assert sorted(result.rejected) == ["goals", "timeline"]


def test_quotes_match_despite_case_and_punctuation() -> None:
    result = verify(company=q("Bloom Bakery", "i run bloom bakery, in alexandria"))
    assert result.contact == {"company": "Bloom Bakery"}


def test_a_contact_detail_must_be_inside_its_quote() -> None:
    # A real quote, but the email in it is not the one claimed
    result = verify(email=q("sara@gmail.com", "My email is sara@bloombakery.com"))
    assert result.contact == {}
    assert result.rejected == ["email"]


def test_an_invalid_email_is_dropped_even_if_quoted() -> None:
    result = LeadInfoExtractor(model=None).verify(
        LeadFacts(email=q("sara@bloom", "write to sara@bloom")), "write to sara@bloom"
    )
    assert result.contact == {}


@pytest.mark.parametrize(
    ("value", "quote", "kept"),
    [
        (2000, "We can spend around 2k a month", True),
        (5000, "We can spend around 2k a month", False),  # number from nowhere
        (2000, "about 24000 a year", True),  # yearly, turned monthly
        (0, "We can spend around 2k a month", False),  # implausible
    ],
)
def test_budget_must_agree_with_its_quote(value, quote, kept) -> None:
    source = SOURCE + "\nabout 24000 a year"
    result = LeadInfoExtractor(model=None).verify(LeadFacts(monthly_budget=q(value, quote)), source)
    assert ("ad_budget" in result.lead) is kept


def test_list_items_are_checked_one_by_one_and_deduplicated() -> None:
    result = verify(
        services=[
            q("Instagram", "more orders from Instagram"),
            q("Google Ads", "maybe Google Ads"),
            q("SEO", "and some SEO too"),  # never said
            q("instagram", "orders from Instagram"),  # duplicate
        ]
    )
    assert result.lead["services"] == ["Instagram", "Google Ads"]
    assert result.rejected == ["services"]


async def test_extract_asks_the_model_and_verifies_its_answer() -> None:
    answer = LeadFacts(
        company=q("Bloom Bakery", "I run Bloom Bakery"),
        industry=q("consulting", "we do management consulting"),  # invented
    )
    model = StubModel(answer)
    result = await LeadInfoExtractor(model).extract(MESSAGES, summary="Asked about prices.")
    assert result.contact == {"company": "Bloom Bakery"}
    assert result.lead == {}
    system, human = model.calls[0]
    assert "exact words" in system.content
    assert "Asked about prices." in human.content
    assert MESSAGES[-1] in human.content


async def test_extract_never_raises() -> None:
    result = await LeadInfoExtractor(StubModel(RuntimeError("provider down"))).extract(MESSAGES)
    assert not result


async def test_extract_skips_the_model_when_there_is_nothing_to_read() -> None:
    model = StubModel(LeadFacts())
    assert not await LeadInfoExtractor(model).extract(["   "])
    assert model.calls == []
