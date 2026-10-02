"""The Cygne agent: a tool-calling loop over any chat model.

Each turn renders a fresh system prompt from the prospect's state, adds the recent
conversation, and lets the model call tools until it has a reply. The model comes from
the provider layer, so the agent runs on Qwen or any other provider unchanged.
"""

from __future__ import annotations

import logging

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from cygne.agent.prompt import PromptContext, build_system_prompt

logger = logging.getLogger(__name__)

# Sent only if the model has nothing to say even when asked directly
FALLBACK_REPLY = "Thanks, got it. Tell me a bit more about what you're looking for?"


class CygneAgent:
    """Wraps a chat model and tools into a runnable account-manager agent."""

    def __init__(
        self, model: BaseChatModel, tools: list[BaseTool], max_iterations: int = 4
    ) -> None:
        self._model = model
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(llm=model, tools=tools, prompt=prompt)
        self._executor = AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=max_iterations,
            handle_parsing_errors=True,
            return_intermediate_steps=True,
        )

    async def respond(
        self,
        message: str,
        context: PromptContext,
        chat_history: list[BaseMessage] | None = None,
    ) -> str:
        """Produce the agent's reply to a prospect message.

        Args:
            message: The latest prospect message.
            context: Context rendered into the system prompt.
            chat_history: Prior turns as LangChain messages (oldest first).

        Returns:
            The agent's natural-language reply, never empty.
        """
        system_prompt = build_system_prompt(context)
        history = chat_history or []
        result = await self._executor.ainvoke(
            {"system_prompt": system_prompt, "input": message, "chat_history": history}
        )
        reply = str(result.get("output") or "").strip()
        if reply:
            return reply

        # Some models end their turn after a tool call without writing anything. Ask
        # once more for the message alone, with no tools, so no action runs twice.
        steps = result.get("intermediate_steps") or []
        done = "; ".join(f"{action.tool} -> {output}" for action, output in steps)
        logger.warning("Empty reply after tools (%s); asking for the message", done or "none")
        try:
            followup = await self._model.ainvoke(
                [
                    SystemMessage(content=system_prompt),
                    *history,
                    HumanMessage(content=message),
                    SystemMessage(
                        content=f"You already did this for the prospect: {done or 'nothing'}. "
                        "Now write your reply to them, following the rules above. "
                        "Reply with the message only."
                    ),
                ]
            )
            reply = str(followup.content).strip()
        except Exception as error:  # noqa: BLE001 - a fallback beats an error to the prospect
            logger.error("Follow-up reply failed: %s", error)
        return reply or FALLBACK_REPLY
