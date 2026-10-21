"""The mastery transport is a WebSocket: uvicorn needs a WS implementation.

Without ``websockets`` or ``wsproto`` installed, uvicorn cannot serve the
upgrade and the browser sees an immediate "websocket error" while HTTP/SSE
surfaces keep working. This guards the dependency declared in ``pyproject``.
"""

from __future__ import annotations

import importlib.util


def test_a_websocket_implementation_is_installed():
    assert importlib.util.find_spec("websockets") or importlib.util.find_spec("wsproto")
