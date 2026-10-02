"""Lead scoring: an explainable fit score.

A lead is scored on five signals, each worth a share of 100 points:

    need          25  what they want from the agency is concrete
    budget        30  monthly budget against the agency's minimum engagement
    timeline      20  how soon they want to start
    authority     15  whether they make the decision
    reachability  10  whether there is an email and a company to follow up with

Each signal is a strength between 0 and 1, so partial information earns partial
points, and the per-signal breakdown is stored with the lead so an operator can see
why a lead scored what it did. The tier is always derived from the score.
"""

from __future__ import annotations

import re

from cygne.db.models import LeadContext, QualificationStatus

WEIGHTS = {"need": 25, "budget": 30, "timeline": 20, "authority": 15, "reachability": 10}

# Tier thresholds on the 0-100 score
TIERS = (
    (65, QualificationStatus.HIGH),
    (40, QualificationStatus.MEDIUM),
    (15, QualificationStatus.LOW),
)

URGENT = re.compile(
    r"\b(now|asap|as soon as possible|immediately|urgent|right away|this (week|month)|"
    r"today|tomorrow)\b"
)
SOON = re.compile(
    r"\b(next (week|month)|soon|this quarter|in (a|\d+|one|two|three) (weeks?|months?)|"
    r"\d+\s*-\s*\d+ (weeks|months))\b"
)
LATER = re.compile(r"\b(later|next (quarter|year)|someday|exploring|just looking|not sure)\b")


def parse_budget(raw: str | None) -> float | None:
    """The first amount in a free-form budget like ``"$3,000/mo"`` or ``"2.5k"``."""
    if not raw:
        return None
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", raw.lower())
    if not match:
        return None
    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None
    return amount * 1000 if match.group(2) else amount


def budget_strength(budget: float | None, minimum: float) -> float:
    """1 at twice the agency minimum or more; little below the minimum."""
    if budget is None or minimum <= 0:
        return 0.0
    ratio = budget / minimum
    if ratio >= 2:
        return 1.0
    if ratio >= 1:
        return 0.75
    if ratio >= 0.5:
        return 0.4
    return 0.15


def timeline_strength(timeline: str | None) -> float:
    if not timeline:
        return 0.0
    text = timeline.lower()
    if URGENT.search(text):
        return 1.0
    if SOON.search(text):
        return 0.7
    if LATER.search(text):
        return 0.25
    return 0.5  # a stated but unclear timeline is still a signal


def need_strength(lead: LeadContext) -> float:
    extra = lead.extra or {}
    items = [*(extra.get("services") or []), *(extra.get("challenges") or [])]
    if len(items) >= 2:
        return 1.0
    return 0.6 if items else 0.0


def authority_strength(lead: LeadContext) -> float:
    decision_maker = (lead.extra or {}).get("decision_maker")
    if decision_maker is True:
        return 1.0
    if decision_maker is False:
        return 0.3  # an influencer still counts for something
    return 0.0


def reachability_strength(lead: LeadContext) -> float:
    prospect = lead.prospect
    if prospect is None:
        return 0.0
    return (0.6 if prospect.email else 0.0) + (0.4 if prospect.company else 0.0)


def qualification_for(score: int) -> QualificationStatus:
    """Map a 0-100 score to its qualification tier."""
    for threshold, tier in TIERS:
        if score >= threshold:
            return tier
    return QualificationStatus.UNQUALIFIED


def score_breakdown(lead: LeadContext, minimum_budget: float = 1000.0) -> dict[str, int]:
    """Points earned per signal, rounded."""
    strengths = {
        "need": need_strength(lead),
        "budget": budget_strength(parse_budget(lead.ad_budget), minimum_budget),
        "timeline": timeline_strength(lead.timeline),
        "authority": authority_strength(lead),
        "reachability": reachability_strength(lead),
    }
    return {signal: round(WEIGHTS[signal] * strength) for signal, strength in strengths.items()}


def score_lead(lead: LeadContext, minimum_budget: float = 1000.0) -> int:
    """Compute and store the lead's score, tier and breakdown; return the score."""
    breakdown = score_breakdown(lead, minimum_budget)
    score = min(100, sum(breakdown.values()))
    lead.score = score
    lead.qualification = qualification_for(score)
    lead.extra = {**(lead.extra or {}), "score_breakdown": breakdown}
    return score
