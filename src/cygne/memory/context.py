"""Assemble runtime context for the agent from stored state.

Bridges the persistence layer (prospects, leads, conversations, messages) and the
agent's prompt/history inputs: the recent-message window becomes chat history, and the
lead record plus conversation summary become the prompt context.
"""

from __future__ import annotations

from datetime import datetime

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from cygne.agent.prompt import PromptContext
from cygne.db.models import Conversation, LeadContext, Message, MessageRole, Prospect


def build_chat_history(messages: list[Message]) -> list[BaseMessage]:
    """Convert stored messages (oldest first) into LangChain chat-history messages."""
    history: list[BaseMessage] = []
    for message in messages:
        if message.role == MessageRole.USER:
            history.append(HumanMessage(content=message.content))
        else:
            history.append(AIMessage(content=message.content))
    return history


def build_prompt_context(
    prospect: Prospect,
    lead: LeadContext,
    conversation: Conversation,
    today: datetime | None = None,
    agency_name: str = "the agency",
) -> PromptContext:
    """Build the system-prompt context from a prospect's current state."""
    today = today or datetime.now()
    extra = lead.extra or {}

    def as_list(key: str) -> list[str]:
        value = extra.get(key)
        return [str(v) for v in value] if isinstance(value, list) else []

    decision_maker = extra.get("decision_maker")
    return PromptContext(
        today=today.strftime("%B %d, %Y"),
        agency_name=agency_name,
        prospect_name=prospect.name,
        company=prospect.company,
        email=prospect.email,
        industry=lead.industry,
        ad_budget=lead.ad_budget,
        timeline=lead.timeline,
        business_stage=lead.business_stage,
        decision_maker=decision_maker if isinstance(decision_maker, bool) else None,
        qualification=lead.qualification.value if lead.qualification else None,
        score=lead.score,
        services=as_list("services"),
        challenges=as_list("challenges"),
        memory_summary=conversation.summary,
        is_returning=bool(conversation.summary),
    )
