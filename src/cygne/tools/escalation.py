"""The ``escalate_to_human`` tool.

Hands the conversation to a human specialist. The operator notification is injected
so the tool stays decoupled from the channel.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# Called when the prospect asks for a human: (prospect_id, reason) -> awaitable.
EscalationNotifier = Callable[[int, str], Awaitable[None]]


class EscalateInput(BaseModel):
    """Why the conversation is being escalated."""

    reason: str = Field(description="Short reason, e.g. 'prospect asked for a human'.")


def build_escalate_tool(
    prospect_id: int, notifier: EscalationNotifier | None = None
) -> StructuredTool:
    """Build an ``escalate_to_human`` tool bound to a prospect and an operator notifier."""

    async def _runner(reason: str) -> str:
        if notifier is not None:
            await notifier(prospect_id, reason)
        return (
            "Escalated to a human specialist. Reassure the prospect briefly that someone "
            "will reach out soon. Do not try to talk them out of it."
        )

    return StructuredTool.from_function(
        coroutine=_runner,
        name="escalate_to_human",
        description=(
            "Call when the prospect asks to speak with a human or real person. Hands off "
            "to a specialist."
        ),
        args_schema=EscalateInput,
    )
