"""Tests for the baseline decision path. Run from the repository root:

    PYTHONPATH=python python3 -m unittest discover -s python/tests
"""

from __future__ import annotations

import unittest

from pairgate import RankRequest, decide
from pairgate.guard import threshold_seconds
from pairgate.rank import score_candidate


def _request(**overrides) -> RankRequest:
    fields = {
        "decision_id": "d1",
        "direction": "AGENT_SURPLUS",
        "line_of_work": "care",
        "anchor_id": "contact-1",
        "candidate_ids": ("a", "b"),
        "cohort": "MATCHED",
        "eligible": True,
    }
    fields.update(overrides)
    return RankRequest(**fields)


class ScoreTests(unittest.TestCase):
    def test_missing_feature_drops_its_weight(self):
        self.assertEqual(score_candidate({"outcome": 1.0}, {"outcome": 1, "resolution": 1}), 1.0)

    def test_equal_weights_average_the_values(self):
        self.assertEqual(
            score_candidate({"outcome": 1.0, "resolution": 0.0}, {"outcome": 1, "resolution": 1}),
            0.5,
        )

    def test_negative_weight_is_rejected(self):
        with self.assertRaises(ValueError):
            score_candidate({"outcome": 1.0}, {"outcome": -1})


class GuardTests(unittest.TestCase):
    def test_small_sample_does_not_set_a_threshold(self):
        self.assertIsNone(threshold_seconds([10, 20, 30]))

    def test_upper_tail_does_not_inflate_the_threshold(self):
        waits = [30, 32, 28, 31, 29, 33, 30, 5000]
        limit = threshold_seconds(waits, buffer_seconds=60)
        self.assertIsNotNone(limit)
        self.assertLess(limit, 120)
        self.assertGreater(limit, 80)


class DecideTests(unittest.TestCase):
    def setUp(self):
        self.weights = {"outcome": 1.0, "resolution": 1.0}
        self.features = {
            "a": {"outcome": 0.2, "resolution": 0.2},
            "b": {"outcome": 0.9, "resolution": 0.9},
        }
        self.queue = [30, 32, 28, 31, 29, 33, 30, 40]

    def test_ineligible_beats_control(self):
        decision = decide(
            _request(eligible=False, cohort="CONTROL"),
            queue_waits=self.queue,
            features_by_candidate=self.features,
            weights=self.weights,
        )
        self.assertEqual(decision.reason, "INELIGIBLE")
        self.assertEqual(decision.disposition, "ORDINARY")

    def test_control_skips_ranking(self):
        decision = decide(
            _request(cohort="CONTROL"),
            queue_waits=self.queue,
            features_by_candidate=self.features,
            weights=self.weights,
        )
        self.assertEqual(decision.reason, "CONTROL")

    def test_agent_surplus_breach_skips_ranking(self):
        decision = decide(
            _request(),
            queue_waits=self.queue,
            anchor_wait_seconds=500,
            features_by_candidate=self.features,
            weights=self.weights,
        )
        self.assertEqual(decision.reason, "BREACH")

    def test_agent_surplus_orders_by_score(self):
        decision = decide(
            _request(),
            queue_waits=self.queue,
            anchor_wait_seconds=10,
            features_by_candidate=self.features,
            weights=self.weights,
        )
        self.assertEqual(decision.disposition, "RANKED")
        self.assertEqual(decision.ordered_candidate_ids, ("b", "a"))

    def test_tie_breaks_by_candidate_id(self):
        features = {
            "b": {"outcome": 0.5},
            "a": {"outcome": 0.5},
        }
        decision = decide(
            _request(),
            queue_waits=self.queue,
            anchor_wait_seconds=0,
            features_by_candidate=features,
            weights={"outcome": 1},
        )
        self.assertEqual(decision.ordered_candidate_ids, ("a", "b"))

    def test_contact_surplus_drops_breached_contacts(self):
        decision = decide(
            _request(direction="CONTACT_SURPLUS", anchor_id="resource-1", candidate_ids=("short", "long")),
            queue_waits=[30, 32, 28, 31, 29, 33, 30, 5000],
            wait_by_candidate={"short": 20, "long": 5000},
            features_by_candidate={
                "short": {"outcome": 0.4},
                "long": {"outcome": 1.0},
            },
            weights={"outcome": 1},
        )
        self.assertEqual(decision.ordered_candidate_ids, ("short",))

    def test_everyone_breached_is_an_ordinary_route(self):
        decision = decide(
            _request(direction="CONTACT_SURPLUS", candidate_ids=("long",)),
            queue_waits=self.queue,
            wait_by_candidate={"long": 5000},
            features_by_candidate={"long": {"outcome": 1}},
            weights={"outcome": 1},
        )
        self.assertEqual(decision.reason, "BREACH")

    def test_no_scores_falls_back(self):
        decision = decide(
            _request(),
            queue_waits=self.queue,
            anchor_wait_seconds=0,
            features_by_candidate={},
            weights=self.weights,
        )
        self.assertEqual(decision.reason, "NO_SCORES")

    def test_over_cap_is_rejected(self):
        with self.assertRaises(ValueError):
            decide(
                _request(candidate_ids=tuple(f"c{i}" for i in range(201))),
                queue_waits=self.queue,
            )

    def test_to_dict_matches_the_result_fields(self):
        decision = decide(
            _request(),
            queue_waits=self.queue,
            anchor_wait_seconds=0,
            features_by_candidate=self.features,
            weights=self.weights,
        )
        body = decision.to_dict()
        self.assertEqual(body["disposition"], "RANKED")
        self.assertEqual(body["scores"][0]["candidateId"], "b")
        self.assertIsNotNone(body["guardThresholdSeconds"])


if __name__ == "__main__":
    unittest.main()
