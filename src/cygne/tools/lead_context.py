"""The ``update_lead_context`` tool.

Lets the agent save business details the prospect has clearly stated and re-score the
lead. Passive extraction fills in details in the background; this tool is for what the
agent has just confirmed in conversation.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from cygne.config import get_settings
from cygne.db.helpers import save_lead_context
from cygne.db.models import Prospect
from cygne.db.session import session_scope
from cygne.leads import score_lead


class UpdateLeadContextInput(BaseModel):
    """Confirmed business details to persist. Omit anything not clearly stated."""

    industry: str | None = Field(None, description="Prospect's industry, e.g. 'ecommerce'.")
    ad_budget: str | None = Field(None, description="Monthly marketing budget, e.g. '3000/month'.")
    business_stage: str | None = Field(
        None, description="One of: startup, growing, established, scaling."
    )
    timeline: str | None = Field(None, description="When they want to start, e.g. 'next month'.")
    services: list[str] | None = Field(
        None, description="What they want from the agency, e.g. ['Google Ads', 'SEO']."
    )
    challenges: list[str] | None = Field(None, description="Problems to solve or goals.")
    decision_maker: bool | None = Field(
        None, description="True if they make the decision, false if someone else does."
    )
    company: str | None = Field(None, description="Company name.")
    email: str | None = Field(None, description="Contact email.")


async def _update_lead_context(prospect_id: int, **fields: object) -> str:
    async with session_scope() as session:
        result = await session.execute(
            select(Prospect).where(Prospect.id == prospect_id).options(selectinload(Prospect.lead))
        )
        prospect = result.scalar_one()

        if fields.get("company"):
            prospect.company = fields.pop("company")  # type: ignore[assignment]
        if fields.get("email"):
            prospect.email = fields.pop("email")  # type: ignore[assignment]

        await save_lead_context(session, prospect.lead, fields)
        score = score_lead(prospect.lead, get_settings().min_monthly_budget)
        return f"Saved. Lead score is now {score} ({prospect.lead.qualification.value})."


def build_update_lead_context_tool(prospect_id: int) -> StructuredTool:
    """Build an ``update_lead_context`` tool bound to a prospect."""

    async def _runner(**fields: object) -> str:
        return await _update_lead_context(prospect_id, **fields)

    return StructuredTool.from_function(
        coroutine=_runner,
        name="update_lead_context",
        description=(
            "Save business details the prospect has clearly stated, and update their lead "
            "score. If what they said was vague, ask them to confirm first."
        ),
        args_schema=UpdateLeadContextInput,
    )
