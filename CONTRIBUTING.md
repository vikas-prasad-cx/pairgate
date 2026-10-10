# Contributing

Pairgate is the real-time join ranker. [Reeforce](https://github.com/vikas-prasad-cx/reeforce) is the intraday schedule control plane. Do not move schedule deltas, queueing-model staffing, or day-ahead optimization into this repository.

## What belongs here

- Eligibility, ranking, the wait guard, cohort measurement, and the interval summary exported to Reeforce.
- Latency on the decision path. A change that adds a network hop to ranking needs an explicit budget note in the pull request.

## What does not belong here

- Meal moves, overflow opens, or other schedule edits. Those stay in Reeforce.
- Vendor routing-platform adapters that name a commercial product. Describe the platform as "the routing engine" and keep product-specific clients out of the core.

## Local check

This repository is documentation and schemas. A pull request should keep `spec/*.schema.json` valid JSON and should update [docs/architecture.md](docs/architecture.md) when a component boundary moves.
