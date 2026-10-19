"""Tool definitions reach the model, and the client parses tool calls safely."""

from __future__ import annotations

import json

import httpx
import pytest

from masterypath.agents import llm as llm_mod
from masterypath.agents.llm import LLMError, OpenAICompatibleClient
from masterypath.capabilities.mastery.tools import TOOL_PARAMETERS, TOOLS, tool_definitions


def test_every_tool_has_a_schema():
    definitions = {item["function"]["name"]: item["function"] for item in tool_definitions(TOOLS)}
    assert set(definitions) == set(TOOLS)
    for name, definition in definitions.items():
        assert definition["description"]
        parameters = definition["parameters"]
        assert parameters["type"] == "object"
        assert "properties" in parameters
        assert name in TOOL_PARAMETERS


def test_required_parameters_match_the_executors():
    assert TOOL_PARAMETERS["mastery_quiz"]["required"] == [
        "knowledge_point_id",
        "question",
        "expected_answer",
    ]
    assert TOOL_PARAMETERS["mastery_grade"]["required"] == ["question_id", "answer"]
    assert TOOL_PARAMETERS["mastery_assess"]["required"] == ["knowledge_point_id", "passed"]


def _mock_post(monkeypatch, handler):
    def _post(url, **kwargs):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        return client.post(url, **kwargs)

    monkeypatch.setattr(llm_mod.httpx, "post", _post)


def test_chat_sends_tools_and_parses_tool_calls(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        names = {item["function"]["name"] for item in body["tools"]}
        assert "mastery_quiz" in names
        assert body["tool_choice"] == "auto"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "mastery_quiz",
                                        "arguments": '{"knowledge_point_id": "k1"}',
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    _mock_post(monkeypatch, handler)
    client = OpenAICompatibleClient(base_url="https://x/v1", api_key="k", model="m")
    response = client.chat(
        [{"role": "user", "content": "hi"}],
        tool_definitions(TOOLS),
    )
    assert response.tool_calls[0].name == "mastery_quiz"
    assert response.tool_calls[0].id == "call-1"
    assert response.tool_calls[0].arguments == {"knowledge_point_id": "k1"}
    assert response.tool_calls[0].parse_error is False


def test_chat_marks_invalid_arguments(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c",
                                    "type": "function",
                                    "function": {"name": "mastery_grade", "arguments": "not json"},
                                }
                            ],
                        }
                    }
                ]
            },
        )

    _mock_post(monkeypatch, handler)
    client = OpenAICompatibleClient(base_url="https://x/v1", api_key="k", model="m")
    call = client.chat([{"role": "user", "content": "hi"}], tool_definitions(TOOLS)).tool_calls[0]
    assert call.parse_error is True
    assert call.arguments == {}


def test_auth_error_is_structured_and_safe(monkeypatch):
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="upstream-secret-token")

    _mock_post(monkeypatch, handler)
    client = OpenAICompatibleClient(base_url="https://x/v1", api_key="bad", model="m")
    with pytest.raises(LLMError) as excinfo:
        client.chat([{"role": "user", "content": "hi"}], [])
    assert excinfo.value.code == "auth_error"
    assert excinfo.value.retryable is False
    assert "upstream-secret-token" not in str(excinfo.value)


def test_opencode_gateway_gets_a_routing_session_header():
    client = OpenAICompatibleClient(
        base_url="https://opencode.ai/zen/go/v1",
        api_key="k",
        model="m",
        session_key="session-1",
    )
    assert client._headers()["x-opencode-session"] == "session-1"

    deepseek = OpenAICompatibleClient(
        base_url="https://api.deepseek.com", api_key="k", model="m"
    )
    assert "x-opencode-session" not in deepseek._headers()


def test_explicit_extra_headers_win():
    client = OpenAICompatibleClient(
        base_url="https://opencode.ai/zen/go/v1",
        api_key="k",
        model="m",
        extra_headers={"x-opencode-session": "explicit", "x-other": "1"},
        session_key="ignored",
    )
    headers = client._headers()
    assert headers["x-opencode-session"] == "explicit"
    assert headers["x-other"] == "1"
