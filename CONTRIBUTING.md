# Contributing

Pairgate is the real-time join ranker. [Reeforce](https://github.com/vikas-prasad-cx/reeforce) is the intraday schedule control plane. Do not move schedule deltas, queueing-model staffing, or day-ahead optimization into this repository.

## What belongs here

- Eligibility, ranking, the wait guard, cohort measurement, and the interval summary exported to Reeforce.
- Latency on the decision path. A change that adds a network hop to ranking needs an explicit budget note in the pull request.

## What does not belong here

- Meal moves, overflow opens, or other schedule edits. Those stay in Reeforce.
- Vendor routing-platform adapters that name a commercial product. Describe the platform as "the routing engine" and keep product-specific clients out of the core.

## Where to start

The join path is open to other projects through two protocols, described in [Using Pairgate from another project](docs/using-from-another-project.md).

- A routing engine or an assistant calls one rank and gets an order or an ordinary-route reason.
- A scheduling agent reads an interval summary and makes its own schedule edit.
- A model writes the cache, or proposes weights, or explains a finished decision. It is not called while the rank is in flight.

A good first change is one of these, in its own pull request:

- An MCP server whose `rank_join` tool matches [examples/mcp-rank-call.json](examples/mcp-rank-call.json).
- An Agent2Agent `SendMessage` handler for the `rank-join` skill in [examples/a2a-rank-task.json](examples/a2a-rank-task.json).
- A slow-side adapter that turns an accepted weight proposal into a score card.
- A port of the baseline ranker, using the decision reasons `RANKED`, `INELIGIBLE`, `CONTROL`, `BREACH`, `EMPTY_POOL`, and `NO_SCORES`.

## Local check

A pull request should keep `spec/*.schema.json` valid JSON and should update [docs/architecture.md](docs/architecture.md) when a component boundary moves. When the baseline ranker is in the tree, Python changes should pass:

```bash
PYTHONPATH=python python3 -m unittest discover -s python/tests
```
