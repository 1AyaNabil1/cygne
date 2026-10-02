"""Read-only queries backing the dashboard."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from cygne.db.helpers import list_qualified_leads
from cygne.db.models import (
    Appointment,
    AppointmentStatus,
    LeadContext,
    Prospect,
    QualificationStatus,
    Quote,
    QuoteStatus,
)
from cygne.db.session import session_scope

QUALIFIED = {QualificationStatus.HIGH, QualificationStatus.MEDIUM}


@dataclass
class LeadRow:
    company: str
    industry: str
    budget: str
    score: int
    qualification: str
    breakdown: str  # points per signal, e.g. "need 25 · budget 30 · timeline 0"


@dataclass
class MeetingRow:
    company: str
    when: str


@dataclass
class DashboardData:
    total_leads: int
    qualified_leads: int
    meetings_booked: int
    quotes_pending: int
    leads: list[LeadRow]
    meetings: list[MeetingRow]


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def load_dashboard() -> DashboardData:
    """Gather the figures and tables shown on the dashboard."""
    async with session_scope() as session:
        leads = await list_qualified_leads(session, min_score=1)
        total_leads = await _count(session, LeadContext)
        quotes_pending = (
            await session.execute(
                select(func.count()).select_from(Quote).where(Quote.status == QuoteStatus.PENDING)
            )
        ).scalar_one()

        meeting_result = await session.execute(
            select(Appointment.scheduled_for, Prospect.company, Prospect.channel_chat_id)
            .join(Prospect, Prospect.id == Appointment.prospect_id)
            .where(Appointment.status == AppointmentStatus.BOOKED)
            .order_by(Appointment.scheduled_for)
        )
        meetings = [
            MeetingRow(
                company=company or chat_id,
                when=when.strftime("%a %Y-%m-%d %H:%M"),
            )
            for when, company, chat_id in meeting_result.all()
        ]

        lead_rows = [
            LeadRow(
                company=lead.prospect.company or lead.prospect.channel_chat_id,
                industry=lead.industry or "—",
                budget=lead.ad_budget or "—",
                score=lead.score,
                qualification=lead.qualification.value,
                breakdown=" · ".join(
                    f"{signal} {points}"
                    for signal, points in (lead.extra or {}).get("score_breakdown", {}).items()
                ),
            )
            for lead in leads
        ]

        return DashboardData(
            total_leads=total_leads,
            qualified_leads=sum(1 for lead in leads if lead.qualification in QUALIFIED),
            meetings_booked=len(meetings),
            quotes_pending=quotes_pending,
            leads=lead_rows,
            meetings=meetings,
        )
