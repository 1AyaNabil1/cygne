"""Tests for the agent's reply handling: a prospect never gets an empty message."""

from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import AIMessage

from cygne.agent.core import FALLBACK_REPLY, CygneAgent
from cygne.agent.prompt import PromptContext


class StubExecutor:
    def __init__(self, output, steps=()):
        self.result = {"output": output, "intermediate_steps": list(steps)}

    async def ainvoke(self, inputs):
        return self.result


class StubModel:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        if isinstance(self.reply, Exception):
            raise self.reply
        return AIMessage(content=self.reply)


def agent_with(executor, model):
    agent = CygneAgent.__new__(CygneAgent)  # skip building a real tool-calling agent
    agent._executor = executor
    agent._model = model
    return agent


CONTEXT = PromptContext(today="October 02, 2026")
SAVED = (SimpleNamespace(tool="update_lead_context"), "Saved. Lead score is now 19 (low).")


async def test_a_normal_reply_is_returned_as_is() -> None:
    model = StubModel("unused")
    reply = await agent_with(StubExecutor("  What's your budget?  "), model).respond("hi", CONTEXT)
    assert reply == "What's your budget?"
    assert model.calls == []


async def test_an_empty_reply_after_a_tool_asks_for_the_message() -> None:
    model = StubModel("Thanks! What's your monthly budget?")
    agent = agent_with(StubExecutor("", [SAVED]), model)
    reply = await agent.respond("We sell cakes online.", CONTEXT)
    assert reply == "Thanks! What's your monthly budget?"
    instruction = model.calls[0][-1].content
    assert "update_lead_context -> Saved." in instruction


async def test_if_the_model_still_says_nothing_the_fallback_is_sent() -> None:
    reply = await agent_with(StubExecutor("", [SAVED]), StubModel("   ")).respond("x", CONTEXT)
    assert reply == FALLBACK_REPLY


async def test_a_failing_follow_up_still_gets_the_fallback() -> None:
    model = StubModel(RuntimeError("rate limited"))
    reply = await agent_with(StubExecutor(None), model).respond("x", CONTEXT)
    assert reply == FALLBACK_REPLY
