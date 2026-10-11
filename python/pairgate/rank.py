"""Weighted score over features already in the cache."""

from __future__ import annotations


def score_candidate(features: dict[str, float], weights: dict[str, float]) -> float | None:
    """Return sum(w * v) / sum(w) over features this candidate has.

    A missing feature drops its weight from the denominator. None means the
    candidate shares no weighted feature with the score card.
    """
    if not weights:
        return None
    numerator = 0.0
    denominator = 0.0
    for name, weight in weights.items():
        if weight <= 0:
            raise ValueError(f"weight for {name} must be > 0")
        if name not in features:
            continue
        value = features[name]
        if value < 0 or value > 1:
            raise ValueError(f"feature {name} must be in 0..1")
        numerator += weight * value
        denominator += weight
    if denominator == 0:
        return None
    return numerator / denominator


def rank_candidates(
    candidate_ids: list[str],
    features_by_candidate: dict[str, dict[str, float]],
    weights: dict[str, float],
) -> list[tuple[str, float]]:
    """Highest score first. Equal scores break by candidate id ascending."""
    scored: list[tuple[str, float]] = []
    for candidate_id in candidate_ids:
        score = score_candidate(features_by_candidate.get(candidate_id, {}), weights)
        if score is None:
            continue
        scored.append((candidate_id, score))
    scored.sort(key=lambda item: (-item[1], item[0]))
    return scored
