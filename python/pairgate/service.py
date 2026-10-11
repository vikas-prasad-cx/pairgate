"""Decision cache and the operations MCP and Agent2Agent call.

An agent sends a rank request. Features, waits, and the live score card are
already here. A weight proposal is stored and does not replace that card.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from pairgate.decide import RankRequest, decide

REQUIRED_RANK_FIELDS = (
    "decisionId",
    "direction",
    "lineOfWork",
    "anchorId",
    "candidateIds",
    "issuedAt",
)


@dataclass
class ScoreCard:
    line_of_work: str
    model_id: str
    weights: dict[str, float]


@dataclass
class StoredDecision:
    result: dict
    line_of_work: str
    issued_at: datetime
    weights: dict[str, float]
    features_by_candidate: dict[str, dict[str, float]]


@dataclass
class DecisionCache:
    score_cards: dict[str, ScoreCard] = field(default_factory=dict)
    features: dict[str, dict[str, float]] = field(default_factory=dict)
    queue_waits: list[float] = field(default_factory=list)
    waits: dict[str, float] = field(default_factory=dict)
    ineligible: set[str] = field(default_factory=set)
    buffer_seconds: float = 60
    decisions: dict[str, StoredDecision] = field(default_factory=dict)
    proposals: list[dict] = field(default_factory=list)

    def put_score_card(self, line_of_work: str, model_id: str, weights: dict[str, float]) -> None:
        self.score_cards[line_of_work] = ScoreCard(line_of_work, model_id, dict(weights))

    @classmethod
    def from_json(cls, payload: dict) -> DecisionCache:
        cache = cls(buffer_seconds=float(payload.get("bufferSeconds", 60)))
        cache.queue_waits = [float(value) for value in payload.get("queueWaits", [])]
        cache.waits = {key: float(value) for key, value in payload.get("waits", {}).items()}
        cache.ineligible = set(payload.get("ineligible", []))
        cache.features = {
            candidate_id: {name: float(value) for name, value in rows.items()}
            for candidate_id, rows in payload.get("features", {}).items()
        }
        for card in payload.get("scoreCards", []):
            cache.put_score_card(
                card["lineOfWork"],
                card.get("modelId", "baseline"),
                {name: float(value) for name, value in card["weights"].items()},
            )
        return cache


class PairgateService:
    """Routing decisions shared by the MCP server and the A2A endpoint."""

    def __init__(self, cache: DecisionCache | None = None) -> None:
        self.cache = cache or DecisionCache()

    def rank_join(self, payload: dict) -> dict:
        request = _rank_request(payload, self.cache)
        card = self.cache.score_cards.get(request.line_of_work)
        weights = {} if card is None else dict(card.weights)
        features = {
            candidate_id: dict(self.cache.features.get(candidate_id, {}))
            for candidate_id in request.candidate_ids
        }
        decision = decide(
            request,
            queue_waits=list(self.cache.queue_waits),
            wait_by_candidate=dict(self.cache.waits),
            anchor_wait_seconds=self.cache.waits.get(request.anchor_id),
            features_by_candidate=features,
            weights=weights,
            buffer_seconds=self.cache.buffer_seconds,
        )
        result = decision.to_dict()
        self.cache.decisions[request.decision_id] = StoredDecision(
            result=result,
            line_of_work=request.line_of_work,
            issued_at=_parse_time(str(payload["issuedAt"])),
            weights=weights,
            features_by_candidate=features,
        )
        return result

    def get_interval_summary(self, payload: dict) -> dict:
        line_of_work = _required_string(payload, "lineOfWork")
        start = _parse_time(payload.get("intervalStart"))
        minutes = int(payload.get("intervalMinutes", 15))
        if minutes < 5 or minutes > 60:
            raise ValueError("intervalMinutes must be from 5 to 60")
        end = start + timedelta(minutes=minutes)
        matched = [
            stored
            for stored in self.cache.decisions.values()
            if stored.line_of_work == line_of_work and start <= stored.issued_at < end
        ]
        breaches = sum(1 for stored in matched if stored.result["reason"] == "BREACH")
        count = len(matched)
        return {
            "intervalStart": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "intervalMinutes": minutes,
            "lineOfWork": line_of_work,
            "decisions": count,
            "breachRate": 0 if count == 0 else breaches / count,
            "scarceCohorts": [],
            "resourceCoverage": [],
        }

    def explain_decision(self, payload: dict) -> dict:
        decision_id = _required_string(payload, "decisionId")
        stored = self.cache.decisions.get(decision_id)
        if stored is None:
            raise ValueError(f"unknown decisionId {decision_id}")
        ordered = stored.result["orderedCandidateIds"]
        top = ordered[0] if ordered else None
        contributions = []
        if top is not None:
            rows = stored.features_by_candidate.get(top, {})
            for name, weight in stored.weights.items():
                if name in rows:
                    contributions.append({"name": name, "weight": weight, "value": rows[name]})
        body = {
            "decisionId": decision_id,
            "featureContributions": contributions,
            "narrative": _narrative(stored.result, top),
        }
        if top is not None:
            body["topCandidateId"] = top
        return body

    def propose_weights(self, payload: dict) -> dict:
        line_of_work = _required_string(payload, "lineOfWork")
        raw_weights = payload.get("proposedWeights")
        if not isinstance(raw_weights, dict) or not raw_weights:
            raise ValueError("proposedWeights must contain at least one weight")
        cleaned: dict[str, float] = {}
        for name, value in raw_weights.items():
            number = float(value)
            if number <= 0:
                raise ValueError(f"weight for {name} must be > 0")
            cleaned[str(name)] = number
        proposal = {
            "lineOfWork": line_of_work,
            "proposedWeights": cleaned,
            "status": "PROPOSED",
        }
        if payload.get("reason") is not None:
            proposal["reason"] = str(payload["reason"])
        self.cache.proposals.append(dict(proposal))
        return proposal


def load_service(path: str) -> PairgateService:
    with open(path, encoding="utf-8") as handle:
        return PairgateService(DecisionCache.from_json(json.load(handle)))


def _rank_request(payload: dict, cache: DecisionCache) -> RankRequest:
    for name in REQUIRED_RANK_FIELDS:
        if name not in payload:
            raise ValueError(f"missing {name}")
    candidate_ids = payload["candidateIds"]
    if not isinstance(candidate_ids, list) or not candidate_ids:
        raise ValueError("candidateIds must be a non-empty list")
    if not all(isinstance(candidate_id, str) and candidate_id for candidate_id in candidate_ids):
        raise ValueError("candidateIds must be non-empty strings")
    anchor_id = str(payload["anchorId"])
    cohort = payload.get("cohort")
    return RankRequest(
        decision_id=str(payload["decisionId"]),
        direction=str(payload["direction"]),
        line_of_work=str(payload["lineOfWork"]),
        anchor_id=anchor_id,
        candidate_ids=tuple(candidate_ids),
        cohort=None if cohort is None else str(cohort),
        eligible=anchor_id not in cache.ineligible,
    )


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("a timestamp must be ISO-8601")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _required_string(payload: dict, name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing {name}")
    return value


def _narrative(result: dict, top: str | None) -> str:
    if result["reason"] == "RANKED" and top is not None:
        score = result["scores"][0]["score"]
        return f"{top} is first with score {score:.2f}. The score came from the live score card."
    return f"No rank was applied. Reason: {result['reason']}."
