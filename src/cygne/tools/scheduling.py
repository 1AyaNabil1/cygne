"""Scheduling tools: ``check_availability`` and ``schedule_meeting``.

Thin wrappers over :class:`~cygne.scheduling.service.SchedulingService`. The agent
chooses a slot by echoing its label (never by computing a date), which removes a whole
class of date-arithmetic errors.
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from cygne.scheduling import SchedulingService
from cygne.scheduling.service import slot_label


async def _check_availability(service: SchedulingService) -> str:
    slots = await service.available_slots()
    if not slots:
        return "No open slots in the next week."
    lines = "\n".join(f"- {slot_label(s)}" for s in slots)
    return "Available slots (offer these to the prospect; to book, pass the exact label):\n" + lines


class ScheduleMeetingInput(BaseModel):
    """The slot to book."""

    slot: str = Field(
        description=(
            "The exact slot label from check_availability, e.g. "
            "'Tuesday, June 23 at 16:00'. Do not invent or reformat it."
        )
    )


def build_check_availability_tool(service: SchedulingService) -> StructuredTool:
    """Build the ``check_availability`` tool."""

    async def _runner() -> str:
        return await _check_availability(service)

    return StructuredTool.from_function(
        coroutine=_runner,
        name="check_availability",
        description=(
            "List real open meeting slots for the next week. Always call this before "
            "booking, and offer the prospect these exact labels."
        ),
    )


def build_schedule_meeting_tool(service: SchedulingService, prospect_id: int) -> StructuredTool:
    """Build a ``schedule_meeting`` tool bound to a prospect."""

    async def _runner(slot: str) -> str:
        return await service.book_by_label(prospect_id, slot)

    return StructuredTool.from_function(
        coroutine=_runner,
        name="schedule_meeting",
        description=(
            "Book a 30-minute strategy call. Pass the exact slot label the prospect chose "
            "from check_availability (e.g. 'Tuesday, June 23 at 16:00'). The prospect must "
            "have an email on file; a calendar invite is emailed automatically."
        ),
        args_schema=ScheduleMeetingInput,
    )
