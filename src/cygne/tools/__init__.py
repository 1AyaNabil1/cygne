"""Agent tools, assembled per-prospect.

Each turn builds tools bound to the prospect being served, so the model can never act on
another prospect's record, plus the optional operator callbacks for the human-in-the-loop
and escalation paths.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from cygne.scheduling import SchedulingService
from cygne.tools.escalation import EscalationNotifier, build_escalate_tool
from cygne.tools.lead_context import build_update_lead_context_tool
from cygne.tools.quote import QuoteNotifier, build_draft_quote_tool
from cygne.tools.scheduling import (
    build_check_availability_tool,
    build_schedule_meeting_tool,
)

__all__ = ["build_agent_tools", "QuoteNotifier", "EscalationNotifier"]


def build_agent_tools(
    prospect_id: int,
    scheduling: SchedulingService,
    quote_notifier: QuoteNotifier | None = None,
    escalation_notifier: EscalationNotifier | None = None,
) -> list[BaseTool]:
    """Return the full tool set for an agent serving a given prospect."""
    return [
        build_update_lead_context_tool(prospect_id),
        build_draft_quote_tool(prospect_id, quote_notifier),
        build_check_availability_tool(scheduling),
        build_schedule_meeting_tool(scheduling, prospect_id),
        build_escalate_tool(prospect_id, escalation_notifier),
    ]
