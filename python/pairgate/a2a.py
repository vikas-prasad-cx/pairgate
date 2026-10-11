"""Agent2Agent JSON-RPC. SendMessage for rank-join uses the same decision as MCP."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pairgate.service import PairgateService

SKILL_METHODS = {
    "rank-join": "rank_join",
    "publish-interval-summary": "get_interval_summary",
    "explain-decision": "explain_decision",
}


def handle_a2a(service: PairgateService, message: dict) -> dict:
    request_id = message.get("id")
    if message.get("method") != "SendMessage":
        return _error(request_id, -32601, "method must be SendMessage")
    params = message.get("params") or {}
    body = params.get("message") or {}
    try:
        data = _data_part(body)
    except ValueError as error:
        return _error(request_id, -32602, str(error))
    skill_id = data.get("skillId")
    method_name = SKILL_METHODS.get(skill_id)
    if method_name is None:
        return _error(request_id, -32602, f"unknown skillId: {skill_id}")
    arguments = {key: value for key, value in data.items() if key != "skillId"}
    try:
        result = getattr(service, method_name)(arguments)
    except (ValueError, TypeError, KeyError) as error:
        return _task(request_id, "TASK_STATE_FAILED", {"error": str(error)})
    return _task(request_id, "TASK_STATE_COMPLETED", result)


def agent_card(public_base: str) -> dict:
    base = public_base.rstrip("/")
    return {
        "name": "Pairgate",
        "description": "Ranks one real-time join and returns the routing decision to the calling agent.",
        "supportedInterfaces": [
            {"url": f"{base}/a2a/v1", "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}
        ],
        "provider": {
            "organization": "Pairgate",
            "url": "https://github.com/vikas-prasad-cx/pairgate",
        },
        "version": "0.1.0",
        "capabilities": {"streaming": False, "pushNotifications": False, "extendedAgentCard": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": [
            {
                "id": "rank-join",
                "name": "Rank one join",
                "description": "Send a rank request. The response is the routing decision.",
                "tags": ["ranking", "join", "realtime"],
            },
            {
                "id": "publish-interval-summary",
                "name": "Publish an interval summary",
                "description": "Return decision counts for a closed interval. No contact profiles.",
                "tags": ["interval-summary"],
            },
            {
                "id": "explain-decision",
                "name": "Explain a completed decision",
                "description": "Explain a decision id that rank-join already returned.",
                "tags": ["explanation"],
            },
        ],
    }


def serve_http(service: PairgateService, host: str, port: int) -> ThreadingHTTPServer:
    handler = _handler_class(service)
    server = ThreadingHTTPServer((host, port), handler)
    return server


def _handler_class(service: PairgateService) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/.well-known/agent-card.json":
                self._send(404, {"error": "not found"})
                return
            host = self.headers.get("Host", "localhost")
            self._send(200, agent_card(f"http://{host}"))

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path not in ("/a2a/v1", "/a2a/v1/"):
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                message = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send(400, _error(None, -32700, "invalid JSON"))
                return
            self._send(200, handle_a2a(service, message))

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    import os

    from pairgate.service import load_service

    path = os.environ.get("PAIRGATE_CACHE")
    service = load_service(path) if path else PairgateService()
    host = os.environ.get("PAIRGATE_HOST", "127.0.0.1")
    port = int(os.environ.get("PAIRGATE_PORT", "8080"))
    server = serve_http(service, host, port)
    server.serve_forever()


def _data_part(message: dict) -> dict:
    for part in message.get("parts") or []:
        if isinstance(part, dict) and isinstance(part.get("data"), dict):
            return part["data"]
    raise ValueError("SendMessage requires one JSON data part")


def _task(request_id: object, state: str, data: dict) -> dict:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "task": {
                "id": str(uuid.uuid4()),
                "status": {"state": state, "timestamp": now},
                "artifacts": [
                    {
                        "artifactId": str(uuid.uuid4()),
                        "parts": [{"data": data, "mediaType": "application/json"}],
                    }
                ],
            }
        },
    }


def _error(request_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    main()
