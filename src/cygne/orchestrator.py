"""Conversation orchestrator — one inbound message, end to end.

Channels (Telegram, CLI) hand a raw message here and get back the agent's reply. The
orchestrator owns the turn: load state, run the agent with prospect-bound tools,
persist the exchange, run passive lead extraction, and roll up the summary.

Persistence is split into committed phases so the agent's tools — which open their own
sessions — always see the prospect and conversation that this turn created.
"""

from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from cygne.agent import CygneAgent
from cygne.calendar import GoogleCalendarClient
from cygne.config import Settings
from cygne.db.helpers import (
    add_message,
    get_or_create_active_conversation,
    get_or_create_prospect,
    recent_messages,
    save_lead_context,
)
from cygne.db.models import Conversation, MessageRole, Prospect
from cygne.db.session import session_scope
from cygne.leads import LeadInfoExtractor, score_lead
from cygne.llm import LLMProvider
from cygne.memory import build_chat_history, build_prompt_context, maybe_summarize
from cygne.scheduling import SchedulingService
from cygne.tools import EscalationNotifier, QuoteNotifier, build_agent_tools

logger = logging.getLogger(__name__)


def _build_calendar(settings: Settings) -> GoogleCalendarClient | None:
    """Build a Google Calendar client if credentials are configured, else None."""
    if not settings.calendar_enabled:
        return None
    return GoogleCalendarClient(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        refresh_token=settings.google_refresh_token,
        calendar_id=settings.google_calendar_id,
    )


class Orchestrator:
    """Runs full conversation turns for a given LLM provider and settings."""

    def __init__(
        self,
        provider: LLMProvider,
        settings: Settings,
        quote_notifier: QuoteNotifier | None = None,
        escalation_notifier: EscalationNotifier | None = None,
    ) -> None:
        self._settings = settings
        self._main_model: BaseChatModel = provider.main_model(settings.main_model)
        self._summary_model: BaseChatModel = provider.summary_model(settings.summary_model)
        self._extractor = LeadInfoExtractor(self._summary_model)
        self._quote_notifier = quote_notifier
        self._escalation_notifier = escalation_notifier
        self._scheduling = SchedulingService(settings, _build_calendar(settings))

    async def handle(self, channel: str, chat_id: str, text: str) -> str:
        """Process one inbound message and return the agent's reply."""
        prospect_id, conversation_id, context, history = await self._load_turn(
            channel, chat_id, text
        )

        agent = CygneAgent(
            self._main_model,
            build_agent_tools(
                prospect_id,
                self._scheduling,
                self._quote_notifier,
                self._escalation_notifier,
            ),
        )
        reply = await agent.respond(text, context, history)

        await self._finalize_turn(conversation_id, prospect_id, text, reply)
        return reply

    async def _load_turn(self, channel: str, chat_id: str, text: str):
        """Commit the inbound message and return everything the agent needs."""
        async with session_scope() as session:
            prospect = await get_or_create_prospect(session, channel, chat_id)
            conversation = await get_or_create_active_conversation(session, prospect.id)
            history = build_chat_history(await recent_messages(session, conversation.id, limit=10))
            context = build_prompt_context(
                prospect, prospect.lead, conversation, agency_name=self._settings.agency_name
            )
            await add_message(session, conversation, MessageRole.USER, text)
            return prospect.id, conversation.id, context, history

    async def _finalize_turn(
        self, conversation_id: int, prospect_id: int, user_text: str, reply: str
    ) -> None:
        """Persist the reply, run passive extraction, and refresh the summary."""
        async with session_scope() as session:
            conversation = await session.get(Conversation, conversation_id)
            await add_message(session, conversation, MessageRole.ASSISTANT, reply)
            await self._passive_extract(session, prospect_id, conversation_id, user_text)
            await maybe_summarize(
                session, self._summary_model, conversation, self._settings.summary_threshold
            )

    async def _passive_extract(
        self, session, prospect_id: int, conversation_id: int, user_text: str
    ) -> None:
        """Best-effort background extraction; never breaks the conversation."""
        try:
            conversation = await session.get(Conversation, conversation_id)
            recent = await recent_messages(session, conversation_id, limit=10)
            prospect_messages = [m.content for m in recent if m.role == MessageRole.USER]
            found = await self._extractor.extract(
                prospect_messages, conversation.summary if conversation else None
            )
            if not found:
                return

            result = await session.execute(
                select(Prospect)
                .where(Prospect.id == prospect_id)
                .options(selectinload(Prospect.lead))
            )
            prospect = result.scalar_one()
            for column in ("name", "email", "company"):
                if found.contact.get(column):
                    setattr(prospect, column, found.contact[column])
            lead_fields = {
                **found.lead,
                "phone": found.contact.get("phone"),
                "website": found.contact.get("website"),
            }
            await save_lead_context(session, prospect.lead, lead_fields)
            score_lead(prospect.lead, self._settings.min_monthly_budget)
        except Exception as error:  # noqa: BLE001
            logger.error("Passive extraction failed: %s", error)
