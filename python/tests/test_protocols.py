"""Agents send a rank request over MCP and A2A and receive the routing decision."""

from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from io import BytesIO

from pairgate.a2a import agent_card, handle_a2a, serve_http
from pairgate.mcp_server import handle_mcp, read_message, serve_stdio, write_message
from pairgate.service import DecisionCache, PairgateService


def _service() -> PairgateService:
    cache = DecisionCache.from_json({
        "bufferSeconds": 60,
        "queueWaits": [30, 32, 28, 31, 29, 33, 30, 40],
        "waits": {"contact-1842": 10},
        "ineligible": ["contact-blocked"],
        "features": {
            "resource-22": {"outcome": 0.9},
            "resource-14": {"outcome": 0.4},
            "resource-7": {"outcome": 0.2},
        },
        "scoreCards": [
            {"lineOfWork": "care", "modelId": "baseline", "weights": {"outcome": 1}}
        ],
    })
    return PairgateService(cache)


def _rank_request(**overrides) -> dict:
    body = {
        "decisionId": "d-1842",
        "direction": "AGENT_SURPLUS",
        "lineOfWork": "care",
        "anchorId": "contact-1842",
        "candidateIds": ["resource-14", "resource-22", "resource-7"],
        "issuedAt": "2026-10-10T23:40:00Z",
        "cohort": "MATCHED",
    }
    body.update(overrides)
    return body


class McpTests(unittest.TestCase):
    def test_rank_join_returns_the_routing_decision(self):
        service = _service()
        listed = handle_mcp(service, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = [tool["name"] for tool in listed["result"]["tools"]]
        self.assertIn("rank_join", names)

        response = handle_mcp(service, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "rank_join", "arguments": _rank_request()},
        })
        result = response["result"]["structuredContent"]
        self.assertEqual(result["disposition"], "RANKED")
        self.assertEqual(result["orderedCandidateIds"][0], "resource-22")
        self.assertFalse(response["result"]["isError"])

    def test_control_cohort_is_an_ordinary_route(self):
        response = handle_mcp(_service(), {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "rank_join", "arguments": _rank_request(cohort="CONTROL", decisionId="d-control")},
        })
        result = response["result"]["structuredContent"]
        self.assertEqual(result["disposition"], "ORDINARY")
        self.assertEqual(result["reason"], "CONTROL")

    def test_proposal_does_not_change_the_live_score_card(self):
        service = _service()
        handle_mcp(service, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "propose_weights",
                "arguments": {
                    "lineOfWork": "care",
                    "proposedWeights": {"outcome": 5, "other": 1},
                    "reason": "cohort outcome moved",
                },
            },
        })
        response = handle_mcp(service, {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "rank_join", "arguments": _rank_request(decisionId="d-after")},
        })
        top = response["result"]["structuredContent"]["scores"][0]
        self.assertEqual(top["candidateId"], "resource-22")
        self.assertEqual(top["score"], 0.9)
        self.assertEqual(service.cache.proposals[0]["status"], "PROPOSED")

    def test_stdio_framing_round_trip(self):
        service = _service()
        inbound = BytesIO()
        write_message(inbound, {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "tools/call",
            "params": {"name": "rank_join", "arguments": _rank_request(decisionId="d-stdio")},
        })
        inbound.seek(0)
        outbound = BytesIO()
        serve_stdio(service, inbound, outbound)
        outbound.seek(0)
        message = read_message(outbound)
        self.assertEqual(message["result"]["structuredContent"]["decisionId"], "d-stdio")


class A2ATests(unittest.TestCase):
    def test_send_message_returns_the_same_decision(self):
        data = _rank_request()
        data["skillId"] = "rank-join"
        response = handle_a2a(_service(), {
            "jsonrpc": "2.0",
            "id": "task-1842",
            "method": "SendMessage",
            "params": {
                "message": {
                    "role": "ROLE_USER",
                    "messageId": "msg-1842",
                    "parts": [{"data": data, "mediaType": "application/json"}],
                }
            },
        })
        artifact = response["result"]["task"]["artifacts"][0]["parts"][0]["data"]
        self.assertEqual(response["result"]["task"]["status"]["state"], "TASK_STATE_COMPLETED")
        self.assertEqual(artifact["orderedCandidateIds"], ["resource-22", "resource-14", "resource-7"])

    def test_ineligible_anchor_is_ordinary(self):
        data = _rank_request(anchorId="contact-blocked", decisionId="d-block")
        data["skillId"] = "rank-join"
        response = handle_a2a(_service(), {
            "jsonrpc": "2.0",
            "id": "task-block",
            "method": "SendMessage",
            "params": {"message": {"parts": [{"data": data}]}},
        })
        artifact = response["result"]["task"]["artifacts"][0]["parts"][0]["data"]
        self.assertEqual(artifact["reason"], "INELIGIBLE")

    def test_http_agent_card_and_rank(self):
        service = _service()
        server = serve_http(service, "127.0.0.1", 0)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            with urllib.request.urlopen(base + "/.well-known/agent-card.json") as response:
                card = json.load(response)
            self.assertEqual(card["skills"][0]["id"], "rank-join")
            self.assertEqual(card["supportedInterfaces"][0]["url"], f"{base}/a2a/v1")
            self.assertEqual(agent_card(base)["name"], "Pairgate")

            data = _rank_request(decisionId="d-http")
            data["skillId"] = "rank-join"
            request = urllib.request.Request(
                base + "/a2a/v1",
                data=json.dumps({
                    "jsonrpc": "2.0",
                    "id": "http-1",
                    "method": "SendMessage",
                    "params": {"message": {"parts": [{"data": data}]}},
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request) as response:
                body = json.load(response)
            artifact = body["result"]["task"]["artifacts"][0]["parts"][0]["data"]
            self.assertEqual(artifact["disposition"], "RANKED")
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
