"""The agent loop IS the tutor (spec 05 §三, ADR-001).

A minimal loop: assemble a mode-framed system prompt, mount every mastery
tool, and run rounds until the model stops calling tools. Mode is enforced at
*call* time by the tools themselves, so a mid-turn mode change is honoured on
the next tool call without re-mounting schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from masterypath.agents.llm import LLMClient
from masterypath.capabilities.mastery import behavior, mode
from masterypath.capabilities.mastery.tools import (
    ToolContext,
    ToolResult,
    tool_definitions,
)


@dataclass
class StreamEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


def _system_prompt(mode_value: Any) -> str:
    current = mode.normalize_mode(mode_value)
    frame = {
        mode.OUTLINE: "You are designing the learning outline with the learner.",
        mode.STUDY: "You are teaching and checking the agreed outline.",
        mode.REVIEW: "You are re-testing objectives the learner already mastered.",
    }[current]
    return (
        "You are the MasteryPath tutor. Decide what to teach and ask; a "
        "deterministic engine decides whether the learner may advance. "
        f"Current mode: {current}. {frame}"
    )


class AgentLoop:
    def __init__(self, tools: dict[str, Any], *, max_rounds: int = 6) -> None:
        self.tools = tools
        self.max_rounds = max_rounds

    def run(
        self,
        client: LLMClient,
        messages: list[dict[str, Any]],
        ctx: ToolContext,
        *,
        system_prompt: str | None = None,
        enforce_mode_set: set[str] | None = None,
    ) -> list[StreamEvent]:
        events: list[StreamEvent] = []
        prompt = system_prompt or _system_prompt(ctx.session_mode)
        history: list[dict[str, Any]] = [{"role": "system", "content": prompt}, *messages]
        tool_defs = tool_definitions(self.tools)
        ended = {"value": False}
        ctx.end_turn = lambda: ended.__setitem__("value", True)
        tool_calls = 0

        for _ in range(self.max_rounds):
            response = client.chat(history, tool_defs)
            if response.text:
                events.append(StreamEvent("text_delta", {"text": response.text}))
            if not response.tool_calls:
                events.append(StreamEvent("turn_end", {"reason": "done"}))
                return events
            # OpenAI requires the assistant turn that requested the calls to be
            # present before its tool results.
            history.append(
                {
                    "role": "assistant",
                    "content": response.text or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                        }
                        for call in response.tool_calls
                    ],
                }
            )
            for call in response.tool_calls:
                tool_calls += 1
                if tool_calls > behavior.MAX_TOOL_CALLS_PER_TURN:
                    # Behavior budget (INV-60): stop making calls this turn.
                    events.append(StreamEvent("turn_end", {"reason": "budget"}))
                    return events
                events.append(
                    StreamEvent(
                        "tool_call",
                        {"name": call.name, "arguments": call.arguments},
                    )
                )
                if call.parse_error:
                    # The provider sent malformed arguments: answer with a failed
                    # result so the model can correct itself instead of crashing.
                    result = ToolResult(ok=False, content="invalid tool arguments")
                else:
                    tool = self.tools.get(call.name)
                    if tool is None:
                        result = ToolResult(ok=False, content=f"unknown tool: {call.name}")
                    else:
                        result = tool.execute(call.arguments, ctx)
                events.append(
                    StreamEvent(
                        "tool_result",
                        {
                            "name": call.name,
                            "ok": result.ok,
                            "content": result.content,
                            "metadata": result.metadata,
                        },
                    )
                )
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result.content,
                    }
                )
                if ended["value"]:
                    # Posing a question ends the turn (INV-44): the learner's
                    # answer arrives as the next message.
                    events.append(StreamEvent("turn_end", {"reason": "card"}))
                    return events
        events.append(StreamEvent("turn_end", {"reason": "max_rounds"}))
        return events


__all__ = ["AgentLoop", "StreamEvent"]
