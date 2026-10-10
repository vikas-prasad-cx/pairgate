# Agent2Agent interface

Pairgate is an agent other agents can discover and delegate to. Discovery uses the [Agent2Agent](https://a2a-protocol.org) agent card at [`.well-known/agent-card.json`](../.well-known/agent-card.json). A scheduling agent, a routing agent, or a supervisor agent reads that card and sends a task. They do not import this repository.

The card in git is a template. `supportedInterfaces[0].url` is `https://pairgate.example/a2a/v1`. A deployment replaces `pairgate.example` with its own host and serves the card at `/.well-known/agent-card.json`. The binding is JSON-RPC 2.0, protocol version 1.0, method `SendMessage`.

## Skills and clocks

| Skill | Who calls it | Clock | Model |
|-------|----------------|-------|-------|
| `rank-join` | Routing agent, when a contact arrives or a person becomes free | One join. Agent surplus near 70 ms, contact surplus under 150 ms. | None. Cache read and arithmetic. |
| `publish-interval-summary` | Scheduling agent, after the interval closes | Seconds, off the join path | None. Aggregates decisions already taken. |
| `explain-decision` | Supervisor agent, after the join is applied | Seconds | Optional. A model may narrate the cached features. |

`rank-join` is the only skill a routing engine calls while someone is waiting. The other two exist so a different agent can do slower work without standing on that path. [Latency](latency.md) still applies: a late rank is discarded.

## What the caller sends

The task message carries one JSON data part (`mediaType: application/json`).

For `rank-join`, the data part is a [rank request](../spec/rank-request.schema.json). The skill id travels with the message so the agent does not infer the task from prose.

For `publish-interval-summary`, the data part names the line of work and the `intervalStart`. The artifact that comes back is an [interval summary](../spec/interval-summary.schema.json). Reeforce, or any other scheduling agent, scores `MOVE_MEAL` and `OPEN_SECTION` from that artifact. Pairgate does not propose the edit.

For `explain-decision`, the data part is a `decisionId` from a join that has already finished. The response may include a short narrative. It is not an instruction to change the join.

## What comes back

A completed task returns one artifact. The artifact's data part is JSON:

- `rank-join` returns `disposition` (`RANKED` or `ORDINARY`), `reason` (`RANKED`, `INELIGIBLE`, `CONTROL`, `BREACH`, `EMPTY_POOL`, or `NO_SCORES`), and `orderedCandidateIds`.
- `publish-interval-summary` returns the interval summary.
- `explain-decision` returns the top candidate id, the feature contributions from the cache, and an optional narrative.

Streaming and push notifications are off. The caller waits for the task result. A rank that misses its budget is an ordinary route, not a streamed partial.

## Boundary

The agent card advertises three skills and no schedule actuator. A caller that wants a meal moved takes the interval summary to its own scheduler. Contact profiles, model weights, and per-contact ranks stay inside Pairgate. That is the same boundary as the [Reeforce contract](reeforce-contract.md).

## Next contributions

- A JSON-RPC `SendMessage` handler that accepts `rank-join` and returns the artifact above, with the budget enforced by discarding a late result.
- Authentication on the interface URL. The template card has no `securitySchemes`. A deployment adds its own scheme and bumps `version`.
- An agent-card test that fails when a skill id, tag, or interface field disappears.
