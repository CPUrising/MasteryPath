"""The agent loop IS the tutor (spec 05 §三, ADR-001).

A minimal loop: assemble a mode-framed system prompt, mount every mastery
tool, and run rounds until the model stops calling tools. Mode is enforced at
*call* time by the tools themselves, so a mid-turn mode change is honoured on
the next tool call without re-mounting schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Iterator

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
    return (
        "You are the MasteryPath tutor. Decide what to teach and ask; a "
        "deterministic engine decides whether the learner may advance. "
        f"Current mode: {current}. {mode.session_frame(current)} "
        "Begin each turn with the mastery_status snapshot supplied by the "
        "runtime, or call mastery_status first; never guess a knowledge_point_id "
        "or the next objective. Trust the engine's next objective and use "
        "mastery_mode when the learner asks for something this mode cannot do."
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
        extra_context: str = "",
    ) -> list[StreamEvent]:
        return list(
            self.stream(
                client,
                messages,
                ctx,
                system_prompt=system_prompt,
                extra_context=extra_context,
            )
        )

    def stream(
        self,
        client: LLMClient,
        messages: list[dict[str, Any]],
        ctx: ToolContext,
        *,
        system_prompt: str | None = None,
        extra_context: str = "",
    ) -> Iterator[StreamEvent]:
        """Yield events as the model produces them, round by round."""
        prompt = system_prompt or _system_prompt(ctx.session_mode)
        if extra_context:
            prompt = f"{prompt}\n\n{extra_context}"
        history: list[dict[str, Any]] = [{"role": "system", "content": prompt}, *messages]
        tool_defs = tool_definitions(self.tools)
        ended = {"value": False}
        ctx.end_turn = lambda: ended.__setitem__("value", True)
        call_count = 0

        for _ in range(self.max_rounds):
            round_text = ""
            calls: list[Any] = []
            streamer = getattr(client, "stream_chat_events", None)
            if streamer is not None:
                for chunk in streamer(history, tool_defs):
                    if chunk.text:
                        round_text += chunk.text
                        yield StreamEvent("text_delta", {"text": chunk.text})
                    if chunk.tool_calls:
                        calls.extend(chunk.tool_calls)
            else:
                # Older/test clients only implement chat: deliver the whole
                # answer as one delta rather than breaking the turn.
                response = client.chat(history, tool_defs)
                if response.text:
                    round_text = response.text
                    yield StreamEvent("text_delta", {"text": response.text})
                calls.extend(response.tool_calls)

            if not calls:
                yield StreamEvent("turn_end", {"reason": "done"})
                return
            # OpenAI requires the assistant turn that requested the calls to be
            # present before its tool results.
            history.append(
                {
                    "role": "assistant",
                    "content": round_text or None,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.name,
                                "arguments": json.dumps(call.arguments),
                            },
                        }
                        for call in calls
                    ],
                }
            )
            for call in calls:
                call_count += 1
                if call_count > behavior.MAX_TOOL_CALLS_PER_TURN:
                    # Behavior budget (INV-60): stop making calls this turn.
                    yield StreamEvent("turn_end", {"reason": "budget"})
                    return
                yield StreamEvent(
                    "tool_call",
                    {"name": call.name, "arguments": call.arguments},
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
                        try:
                            result = tool.execute(call.arguments, ctx)
                        except Exception as exc:  # noqa: BLE001 - a tool must not kill the turn
                            result = ToolResult(
                                ok=False, content=f"tool failed: {exc}"
                            )
                yield StreamEvent(
                    "tool_result",
                    {
                        "name": call.name,
                        "ok": result.ok,
                        "content": result.content,
                        "metadata": result.metadata,
                    },
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
                    yield StreamEvent("turn_end", {"reason": "card"})
                    return
        yield StreamEvent("turn_end", {"reason": "max_rounds"})


__all__ = ["AgentLoop", "StreamEvent"]
