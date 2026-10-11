"""MCP stdio server. rank_join calls the same decision path as A2A."""

from __future__ import annotations

import json
import sys
from typing import BinaryIO

from pairgate.service import PairgateService, load_service

PROTOCOL_VERSION = "2025-11-25"
SERVER_INFO = {"name": "pairgate", "version": "0.1.0"}

RANK_INPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decisionId", "direction", "lineOfWork", "anchorId", "candidateIds", "issuedAt"],
    "properties": {
        "decisionId": {"type": "string"},
        "direction": {"enum": ["AGENT_SURPLUS", "CONTACT_SURPLUS"]},
        "lineOfWork": {"type": "string"},
        "anchorId": {"type": "string"},
        "candidateIds": {"type": "array", "minItems": 1, "maxItems": 200, "items": {"type": "string"}},
        "issuedAt": {"type": "string"},
        "cohort": {"enum": ["MATCHED", "CONTROL"]},
    },
}

TOOLS = [
    {
        "name": "rank_join",
        "title": "Rank one join",
        "description": "Rank a capped pool and return RANKED or ORDINARY. Reads the decision cache only.",
        "inputSchema": RANK_INPUT_SCHEMA,
    },
    {
        "name": "get_interval_summary",
        "title": "Get the interval summary",
        "description": "Counts of decisions already taken in one interval. No contact profiles and no weights.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["lineOfWork", "intervalStart"],
            "properties": {
                "lineOfWork": {"type": "string"},
                "intervalStart": {"type": "string"},
                "intervalMinutes": {"type": "integer"},
            },
        },
    },
    {
        "name": "explain_decision",
        "title": "Explain a completed decision",
        "description": "Feature contributions for a join that has already been returned. Not a second rank.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["decisionId"],
            "properties": {"decisionId": {"type": "string"}},
        },
    },
    {
        "name": "propose_weights",
        "title": "Propose objective weights",
        "description": "Record a weight proposal. The live score card does not change.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["lineOfWork", "proposedWeights"],
            "properties": {
                "lineOfWork": {"type": "string"},
                "proposedWeights": {"type": "object"},
                "reason": {"type": "string"},
            },
        },
    },
]

TOOL_METHODS = {
    "rank_join": "rank_join",
    "get_interval_summary": "get_interval_summary",
    "explain_decision": "explain_decision",
    "propose_weights": "propose_weights",
}


def handle_mcp(service: PairgateService, message: dict) -> dict | None:
    method = message.get("method")
    if method == "notifications/initialized":
        return None
    request_id = message.get("id")
    if method == "initialize":
        return _result(request_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        })
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        return _call_tool(service, request_id, message.get("params") or {})
    if method == "ping":
        return _result(request_id, {})
    return _error(request_id, -32601, f"method not found: {method}")


def _call_tool(service: PairgateService, request_id: object, params: dict) -> dict:
    name = params.get("name")
    method_name = TOOL_METHODS.get(name)
    if method_name is None:
        return _error(request_id, -32602, f"unknown tool: {name}")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return _error(request_id, -32602, "arguments must be an object")
    try:
        body = getattr(service, method_name)(arguments)
    except (ValueError, TypeError, KeyError) as error:
        return _result(request_id, {
            "content": [{"type": "text", "text": str(error)}],
            "isError": True,
        })
    text = json.dumps(body)
    return _result(request_id, {
        "content": [{"type": "text", "text": text}],
        "structuredContent": body,
        "isError": False,
    })


def read_message(stream: BinaryIO) -> dict | None:
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("ascii").strip()
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.lower()] = value.strip()
    if "content-length" not in headers:
        raise ValueError("MCP message is missing Content-Length")
    length = int(headers["content-length"])
    body = stream.read(length)
    if len(body) != length:
        raise ValueError("MCP message ended early")
    return json.loads(body.decode("utf-8"))


def write_message(stream: BinaryIO, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    stream.write(body)
    stream.flush()


def serve_stdio(service: PairgateService, inbound: BinaryIO, outbound: BinaryIO) -> None:
    while True:
        message = read_message(inbound)
        if message is None:
            return
        response = handle_mcp(service, message)
        if response is not None:
            write_message(outbound, response)


def main() -> None:
    import os

    path = os.environ.get("PAIRGATE_CACHE")
    service = load_service(path) if path else PairgateService()
    serve_stdio(service, sys.stdin.buffer, sys.stdout.buffer)


def _result(request_id: object, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: object, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


if __name__ == "__main__":
    main()
