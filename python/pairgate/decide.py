"""One join: eligibility, cohort, wait guard, then the baseline rank."""

from __future__ import annotations

from dataclasses import dataclass

from pairgate.guard import is_breached, threshold_seconds
from pairgate.rank import rank_candidates

MAX_CANDIDATES = 200


@dataclass(frozen=True)
class RankRequest:
    decision_id: str
    direction: str
    line_of_work: str
    anchor_id: str
    candidate_ids: tuple[str, ...]
    cohort: str | None = None
    eligible: bool = True


@dataclass(frozen=True)
class Decision:
    decision_id: str
    disposition: str
    reason: str
    ordered_candidate_ids: tuple[str, ...]
    scores: tuple[tuple[str, float], ...]
    guard_threshold_seconds: float | None

    def to_dict(self) -> dict:
        return {
            "decisionId": self.decision_id,
            "disposition": self.disposition,
            "reason": self.reason,
            "orderedCandidateIds": list(self.ordered_candidate_ids),
            "scores": [
                {"candidateId": candidate_id, "score": score}
                for candidate_id, score in self.scores
            ],
            "guardThresholdSeconds": self.guard_threshold_seconds,
        }


def decide(
    request: RankRequest,
    *,
    queue_waits: list[float],
    wait_by_candidate: dict[str, float] | None = None,
    anchor_wait_seconds: float | None = None,
    features_by_candidate: dict[str, dict[str, float]] | None = None,
    weights: dict[str, float] | None = None,
    buffer_seconds: float = 60,
) -> Decision:
    """Apply the decision path and return a rank result.

    ``queue_waits`` is the live wait sample used to set the guard. For agent
    surplus, ``anchor_wait_seconds`` is the arriving contact's wait (0 when
    the contact just arrived). For contact surplus, ``wait_by_candidate`` is
    the wait of each waiting contact; a missing entry is treated as 0.
    """
    if request.direction not in ("AGENT_SURPLUS", "CONTACT_SURPLUS"):
        raise ValueError("direction must be AGENT_SURPLUS or CONTACT_SURPLUS")
    if request.cohort not in (None, "MATCHED", "CONTROL"):
        raise ValueError("cohort must be MATCHED or CONTROL")
    if len(request.candidate_ids) > MAX_CANDIDATES:
        raise ValueError("candidateIds exceeds 200")

    waits = wait_by_candidate or {}
    features = features_by_candidate or {}
    live_weights = weights or {}
    limit = threshold_seconds(list(queue_waits), buffer_seconds)

    if len(request.candidate_ids) == 0:
        return _ordinary(request, "EMPTY_POOL", limit)
    if not request.eligible:
        return _ordinary(request, "INELIGIBLE", limit)
    if request.cohort == "CONTROL":
        return _ordinary(request, "CONTROL", limit)

    if request.direction == "AGENT_SURPLUS":
        anchor_wait = 0 if anchor_wait_seconds is None else anchor_wait_seconds
        if is_breached(anchor_wait, limit):
            return _ordinary(request, "BREACH", limit)
        pool = list(request.candidate_ids)
    else:
        pool = [
            candidate_id
            for candidate_id in request.candidate_ids
            if not is_breached(waits.get(candidate_id, 0), limit)
        ]
        if not pool:
            return _ordinary(request, "BREACH", limit)

    scored = rank_candidates(pool, features, live_weights)
    if not scored:
        return _ordinary(request, "NO_SCORES", limit)
    return Decision(
        decision_id=request.decision_id,
        disposition="RANKED",
        reason="RANKED",
        ordered_candidate_ids=tuple(candidate_id for candidate_id, _score in scored),
        scores=tuple(scored),
        guard_threshold_seconds=limit,
    )


def _ordinary(request: RankRequest, reason: str, limit: float | None) -> Decision:
    return Decision(
        decision_id=request.decision_id,
        disposition="ORDINARY",
        reason=reason,
        ordered_candidate_ids=(),
        scores=(),
        guard_threshold_seconds=limit,
    )
