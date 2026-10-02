"""Passive lead extraction, grounded in the prospect's own words.

After each turn, a cheap model reads the prospect's recent messages and returns what
they said about their business. Every fact must come with the exact words it was taken
from, and a fact is kept only if those words really appear in the prospect's messages
and agree with the value (an email must be in its quote, a budget must match the amount
quoted). Facts the model inferred, or took from the assistant's own questions, have no
quote to point to and are dropped. Checking the evidence is more reliable than asking
the model how confident it is.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from cygne.leads.dedup import deduplicate
from cygne.leads.scoring import parse_budget

logger = logging.getLogger(__name__)


class Quoted(BaseModel):
    value: str
    quote: str = Field(description="The prospect's exact words this was taken from.")


class QuotedAmount(BaseModel):
    value: float = Field(description="Per month, in the prospect's currency; 5k is 5000.")
    quote: str = Field(description="The prospect's exact words this was taken from.")


class QuotedFlag(BaseModel):
    value: bool
    quote: str = Field(description="The prospect's exact words this was taken from.")


class QuotedStage(BaseModel):
    value: Literal["startup", "growing", "established", "scaling"]
    quote: str = Field(description="The prospect's exact words this was taken from.")


class LeadFacts(BaseModel):
    """What the prospect has said about themselves and their business. Leave out any
    field they have not stated."""

    name: Quoted | None = None
    email: Quoted | None = None
    phone: Quoted | None = None
    company: Quoted | None = None
    website: Quoted | None = None
    industry: Quoted | None = Field(None, description="What the business does, in a few words.")
    business_stage: QuotedStage | None = None
    monthly_budget: QuotedAmount | None = Field(None, description="Marketing budget per month.")
    timeline: Quoted | None = Field(None, description="When they want to start.")
    decision_maker: QuotedFlag | None = Field(
        None,
        description="True if they own the business or make the call; false if someone else does.",
    )
    services: list[Quoted] = Field(
        default_factory=list, description="What they want from the agency: ads, SEO, a website..."
    )
    goals: list[Quoted] = Field(
        default_factory=list, description="Problems they want solved or results they want."
    )
    current_marketing: list[Quoted] = Field(
        default_factory=list, description="What they already do for marketing."
    )


INSTRUCTIONS = """You keep the notes for a marketing agency's sales team. You will be \
shown messages written by a prospect. Record what the prospect has told us about \
themselves and their business.

- Record only what the prospect stated. Questions, guesses and suggestions are not facts.
- For every fact, put the prospect's exact words in `quote`, copied character for \
character. If you can't point to their words, leave the fact out.
- Leave out anything hedged as hypothetical ("if we ever...", "maybe someday").
- A budget is per month. Turn "5k" into 5000 and a yearly amount into a monthly one."""

EMAIL = re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$")
MAX_MONTHLY_BUDGET = 1_000_000
CONTACT_FIELDS = ("name", "email", "phone", "company", "website")
# LeadFacts list field -> key in the lead's stored context
LIST_FIELDS = {
    "services": "services",
    "goals": "challenges",
    "current_marketing": "current_marketing",
}


def _clean(text: str) -> str:
    return " ".join(re.sub(r"[^\w@.+\-\s]", " ", text.casefold()).split())


@dataclass
class ExtractionResult:
    """Facts that passed the evidence check, split by where they are stored."""

    contact: dict[str, str] = field(default_factory=dict)  # name, email, phone, company, website
    lead: dict[str, object] = field(default_factory=dict)  # lead-context fields
    rejected: list[str] = field(default_factory=list)  # fields dropped, for logs

    def __bool__(self) -> bool:
        return bool(self.contact or self.lead)


class LeadInfoExtractor:
    """Extracts grounded lead facts from the prospect's side of a conversation."""

    def __init__(self, model: BaseChatModel, match_threshold: int = 90) -> None:
        self.model = model
        self.match_threshold = match_threshold

    async def extract(
        self, prospect_messages: list[str], summary: str | None = None
    ) -> ExtractionResult:
        """Facts from ``prospect_messages`` (oldest first) that their words support.

        ``summary`` gives earlier context, but facts must be quoted from the messages.
        Never raises: a failed extraction returns an empty result.
        """
        messages = [m for m in prospect_messages if m.strip()]
        if not messages:
            return ExtractionResult()
        listing = "\n".join(f"- {m}" for m in messages)
        context = f"Earlier in the conversation: {summary}\n\n" if summary else ""
        request = f"{context}The prospect's messages, oldest first:\n{listing}"
        try:
            facts = await self.model.with_structured_output(
                LeadFacts, method="function_calling"
            ).ainvoke([SystemMessage(content=INSTRUCTIONS), HumanMessage(content=request)])
        except Exception as error:  # noqa: BLE001 - extraction must never break the chat
            logger.error("Lead extraction failed: %s", error)
            return ExtractionResult()
        if not isinstance(facts, LeadFacts):
            return ExtractionResult()
        return self.verify(facts, " \n ".join(messages))

    def _said(self, quote: str, source_clean: str) -> bool:
        q = _clean(quote)
        return len(q) >= 2 and (
            q in source_clean or fuzz.partial_ratio(q, source_clean) >= self.match_threshold
        )

    def verify(self, facts: LeadFacts, source: str) -> ExtractionResult:
        """Keep the facts whose quotes are in ``source`` and agree with their values."""
        source_clean = _clean(source)
        result = ExtractionResult()

        for name in CONTACT_FIELDS:
            fact: Quoted | None = getattr(facts, name)
            if fact is None:
                continue
            value = fact.value.strip()
            # A contact detail must appear in the words it was quoted from
            grounded = self._said(fact.quote, source_clean) and _clean(value) in _clean(fact.quote)
            if grounded and (name != "email" or EMAIL.match(value)):
                result.contact[name] = value
            else:
                result.rejected.append(name)

        for name in ("industry", "timeline", "business_stage", "decision_maker"):
            single = getattr(facts, name)
            if single is None:
                continue
            if self._said(single.quote, source_clean):
                value = single.value.strip() if isinstance(single.value, str) else single.value
                result.lead[name] = value
            else:
                result.rejected.append(name)

        budget = facts.monthly_budget
        if budget is not None:
            quoted = parse_budget(budget.quote)
            plausible = 0 < budget.value <= MAX_MONTHLY_BUDGET
            # Allow a yearly amount turned monthly, but not a number from nowhere
            consistent = quoted is None or quoted in (budget.value, budget.value * 12)
            if self._said(budget.quote, source_clean) and plausible and consistent:
                result.lead["ad_budget"] = f"{budget.value:g}/month"
            else:
                result.rejected.append("monthly_budget")

        for name, key in LIST_FIELDS.items():
            facts_list: list[Quoted] = getattr(facts, name)
            items = [f.value.strip() for f in facts_list if self._said(f.quote, source_clean)]
            if len(items) < len(facts_list):
                result.rejected.append(name)
            if items:
                result.lead[key] = deduplicate(items)

        if result.rejected:
            logger.info("Dropped unsupported lead facts: %s", sorted(set(result.rejected)))
        return result
