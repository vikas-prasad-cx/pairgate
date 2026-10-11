# Baseline ranker

A Python implementation of the join path: eligibility, cohort, wait guard, and a weighted score over features already in the cache. There are no third-party dependencies.

```bash
PYTHONPATH=python python3 -m unittest discover -s python/tests
```

`decide` returns a result shaped like [spec/rank-result.schema.json](../spec/rank-result.schema.json). `RANKED` is an order the routing engine can apply. `ORDINARY` means the engine should use its own fallback.

The package does not load a model or fetch a profile. A contributor who wants a different score replaces `pairgate.rank.score_candidate` and keeps `decide` on the same inputs.

## Calling it

`pairgate.mcp_server` is the MCP stdio server. `pairgate.a2a` is the Agent2Agent HTTP endpoint. Both read a decision cache from `PAIRGATE_CACHE` and run `rank_join` / `rank-join` through `decide`.

```bash
PYTHONPATH=python PAIRGATE_CACHE=python/decision-cache.example.json python3 -m pairgate.mcp_server
PYTHONPATH=python PAIRGATE_CACHE=python/decision-cache.example.json python3 -m pairgate.a2a
```

`cache.json` holds `scoreCards`, `features`, `queueWaits`, `waits`, and `ineligible`. The agent sends only the rank request. A `propose_weights` call is stored as `PROPOSED` and does not replace the score card.
