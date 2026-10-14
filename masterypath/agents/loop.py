"""The agent loop IS the tutor (spec 05 §三, ADR-001).

A minimal loop: assemble a mode-framed system prompt, mount every mastery
tool, and run rounds until the model stops calling tools. Mode is enforced at
*call* time by the tools themselves, so a mid-turn mode change is honoured on
the next tool call without re-mounting schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from masterypath.agents.llm import LLMClient
from masterypath.capabilities.mastery import mode
from masterypath.capabilities.mastery.tools import ToolContext, ToolResult


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
        tool_names = sorted(self.tools)
        ended = {"value": False}
        ctx.end_turn = lambda: ended.__setitem__("value", True)

        for _ in range(self.max_rounds):
            response = client.chat(history, tool_names)
            if response.text:
                events.append(StreamEvent("text_delta", {"text": response.text}))
            if not response.tool_calls:
                events.append(StreamEvent("turn_end", {"reason": "done"}))
                return events
            for call in response.tool_calls:
                events.append(
                    StreamEvent(
                        "tool_call",
                        {"name": call.name, "arguments": call.arguments},
                    )
                )
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
                        "name": call.name,
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
