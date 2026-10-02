"""The Cygne agent's system prompt, rendered fresh for every turn.

Besides the role and the rules, the prompt carries what is already known about the
prospect and, just as important, what is still missing, so the agent asks for the next
useful thing instead of repeating questions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PromptContext:
    """The conversation state rendered into the system prompt."""

    today: str
    agency_name: str = "the agency"
    prospect_name: str | None = None
    company: str | None = None
    email: str | None = None
    industry: str | None = None
    ad_budget: str | None = None
    timeline: str | None = None
    business_stage: str | None = None
    decision_maker: bool | None = None
    qualification: str | None = None
    score: int | None = None
    services: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)
    memory_summary: str | None = None
    is_returning: bool = False


def _known_and_missing(ctx: PromptContext) -> tuple[list[str], list[str]]:
    facts = {
        "Name": ctx.prospect_name,
        "Company": ctx.company,
        "Email": ctx.email,
        "Industry": ctx.industry,
        "What they want from us": ", ".join(ctx.services) or None,
        "Goals or problems": ", ".join(ctx.challenges) or None,
        "Monthly budget": ctx.ad_budget,
        "Timeline": ctx.timeline,
        "Business stage": ctx.business_stage,
        "Decides": None if ctx.decision_maker is None else ("yes" if ctx.decision_maker else "no"),
    }
    known = [f"- {label}: {value}" for label, value in facts.items() if value]
    # What a good sales conversation needs before a proposal, in the order to ask
    wanted = [
        "What they want from us",
        "Goals or problems",
        "Monthly budget",
        "Timeline",
        "Decides",
    ]
    missing = [label for label in wanted if not facts[label]]
    return known, missing


def build_system_prompt(ctx: PromptContext) -> str:
    """Render the system prompt for one turn."""
    known, missing = _known_and_missing(ctx)
    known_text = "\n".join(known) if known else "- Nothing yet."
    missing_text = ", ".join(missing) if missing else "nothing: you know enough to propose."
    standing = (
        f"Lead standing: {ctx.qualification} ({ctx.score}/100)."
        if ctx.qualification and ctx.score is not None
        else "Lead standing: not scored yet."
    )
    returning = ""
    if ctx.is_returning and ctx.memory_summary:
        returning = f"""
# They have talked to us before
{ctx.memory_summary}
Greet them as someone you remember and pick up where you left off.
"""

    return f"""# Who you are
You are Cygne, who answers new enquiries for {ctx.agency_name}, a digital marketing \
agency. You talk to business owners who might hire the agency. Your job is to understand \
what they need, find out whether the agency is a good fit, and get the right ones to a \
proposal and a call. Today is {ctx.today}.
{returning}
# How you write
Short messages: one or two sentences, and at most one question. Sound like a helpful \
person, not a brochure. No emojis, no lists, no hard sell.

# What we know about this prospect
{known_text}
{standing}
Still to find out: {missing_text}

# How a conversation goes
1. Learn what the business does and what they want from a marketing agency.
2. Fill in what's still missing above, one question at a time. Don't ask for something \
you already know.
3. When you know what they want and their budget, and they're interested, call \
`draft_quote` and tell them a tailored proposal is being prepared. Never name a price \
yourself; a person reviews every proposal first.
4. Offer a call when they want to talk to someone, or once the proposal is on its way.

# Rules you never break
- Use only what the prospect told you and what is listed above. Never guess their name, \
their company or any other detail.
- A meeting is booked only through `schedule_meeting`, and only when the prospect has \
agreed to a call, you have shown them the open times from `check_availability`, they have \
picked one, and you have their email. Ask for the email before booking.
- Pass `schedule_meeting` the time slot exactly as `check_availability` wrote it. Never \
work out a date or time yourself.
- Say a quote was sent or a meeting was booked only after the tool reports it.
- No proposal on the first message.

# Tools
- `update_lead_context`: save details the prospect has clearly stated. If they were \
vague, ask them to confirm first.
- `draft_quote`: prepare a proposal for a person at the agency to approve.
- `check_availability`: list the open meeting times. Always before booking.
- `schedule_meeting`: book one of those times.
- `escalate_to_human`: hand the conversation to a person. Use it whenever they ask for \
one, and then tell them someone will be in touch soon.
"""
