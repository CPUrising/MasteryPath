"""Task Model — a small background model for drafts (spec 05 §八).

It writes a *suggested next question* (a draft the learner accepts with Tab) and
can name a session. Per ADR-014 it depends only on ``LLMClient`` and always has
a deterministic fallback, so it works with no provider and is testable offline.
"""

from __future__ import annotations

from typing import Any, Callable

from masterypath.agents.llm import LLMClient

_SYSTEM = (
    "You write ONE short next question for a mastery-learning tutor, in the "
    "learner's language. Output only the question, no preamble."
)


class TaskModel:
    def __init__(self, client_factory: Callable[[], LLMClient] | None = None) -> None:
        self.client_factory = client_factory

    def suggest_question(
        self, path_state: dict[str, Any], recent: list[str] | None = None
    ) -> str:
        """A draft question for the composer. Never raises."""
        if self.client_factory is not None:
            try:
                client = self.client_factory()
                messages = [
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": _prompt(path_state, recent or [])},
                ]
                response = client.chat(messages, [])
                text = (response.text or "").strip()
                if text:
                    return text
            except Exception:
                pass
        return self._fallback(path_state)

    def suggest_session_name(self, goal: str) -> str:
        text = (goal or "").strip()
        return text[:40] if text else "新学习会话"

    @staticmethod
    def _fallback(path_state: dict[str, Any]) -> str:
        next_step = path_state.get("next", {}) if isinstance(path_state, dict) else {}
        action = next_step.get("action")
        name = next_step.get("knowledge_point_name") or "这个知识点"
        if action == "answer_pending":
            return "先作答上面那张卡片，再继续。"
        if action == "review":
            return f"复习一下：{name} 你还记得吗？请用自己的话说说。"
        if action == "complete":
            return "这条路径的目标已全部掌握，要不要开始一个新主题？"
        if action == "assess":
            return f"请用你自己的话解释 {name}，并举一个例子。"
        return f"关于 {name}，你最先想到的是什么？"


def _prompt(path_state: dict[str, Any], recent: list[str]) -> str:
    next_step = path_state.get("next", {}) if isinstance(path_state, dict) else {}
    lines = [
        f"Current action: {next_step.get('action', '')}",
        f"Objective: {next_step.get('knowledge_point_name', '')}",
        f"Objective type: {next_step.get('knowledge_point_type', '')}",
    ]
    if recent:
        lines.append("Recent conversation:")
        lines.extend(f"- {item}" for item in recent[-6:])
    return "\n".join(lines)


__all__ = ["TaskModel"]
