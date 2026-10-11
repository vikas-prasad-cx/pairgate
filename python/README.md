# Baseline ranker

A Python implementation of the join path: eligibility, cohort, wait guard, and a weighted score over features already in the cache. There are no third-party dependencies.

```bash
PYTHONPATH=python python3 -m unittest discover -s python/tests
```

`decide` returns a result shaped like [spec/rank-result.schema.json](../spec/rank-result.schema.json). `RANKED` is an order the routing engine can apply. `ORDINARY` means the engine should use its own fallback.

The package does not load a model, fetch a profile, or publish an interval summary. Those stay on the slow side. A contributor who wants a different score replaces `pairgate.rank.score_candidate` and keeps `decide` on the same inputs.

## Next contributions

- A cache reader that supplies `weights` and `features_by_candidate` from a score card.
- The same decision path in another language, with these tests as the oracle.
- An MCP `rank_join` handler that calls `decide` and refuses a request of more than 200 candidates.
