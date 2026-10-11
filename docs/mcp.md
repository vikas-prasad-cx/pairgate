# Model Context Protocol interface

Any MCP host can call Pairgate. An assistant, a workflow, or another project's agent opens a session, lists tools, and calls the one it needs. The contract is [spec/mcp-server.json](../spec/mcp-server.json), aligned with [MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25). This repository does not yet run a server. An implementation advertises these tools, resources, and prompts and no others on the public surface.

## Tools

| Tool | Clock | What the caller gets |
|------|-------|----------------------|
| `rank_join` | One join. Inside the [latency budget](latency.md). | `RANKED` with ordered candidate ids, or `ORDINARY` with a reason. |
| `get_interval_summary` | After the interval closes. | Breach rate, scarce cohorts, resource coverage. |
| `explain_decision` | After the join is applied. | Feature contributions from the cache, and an optional narrative. |
| `propose_weights` | Slow side, from cohort results. | A document with `status: PROPOSED`. It does not change live weights. |

`rank_join` takes the same fields as a [rank request](../spec/rank-request.schema.json). The routing engine may call it while a contact is waiting. The other three tools are how a model-using host participates without standing on that path.

`explain_decision` may attach a model narrative. The narrative is for a supervisor. It is not a second rank, and it cannot move a meal.

`propose_weights` is the write a model is allowed to make. The tool records a proposal. A person or a policy accepts it. Only then does the slow side write a score card into the decision cache. The next join reads the card. The join that is in flight does not.

## Resources

| URI | Body |
|-----|------|
| `pairgate://spec/rank-request` | The rank-request schema. |
| `pairgate://spec/interval-summary` | The interval-summary schema. |
| `pairgate://interval/{lineOfWork}/latest` | The latest closed summary for that line of work. |

Resources are context. They are not a side door onto contact profiles. A host that needs the summary for a scheduling decision reads `pairgate://interval/{lineOfWork}/latest` or calls `get_interval_summary`.

## Prompt

`review-weight-proposal` asks a supervisor to accept or reject a proposal. Arguments are the line of work and the proposal JSON. The prompt must not be filled with contact profiles or raw feature rows.

## What a host sends

`rank_join` is a normal `tools/call`. The arguments are the rank request. The tool result's `structuredContent` is the rank result: `disposition`, `reason`, and `orderedCandidateIds`. The same call is safe to repeat for the same `decisionId` while the cache is unchanged (`idempotentHint: true`). `propose_weights` is not idempotent: each call records a proposal.

## Next contributions

- A stdio MCP server that implements `rank_join` against the decision cache and rejects a call that would fetch a profile.
- A resources reader for `pairgate://interval/{lineOfWork}/latest`.
- A client in another repository that lists these tools and never vendors a Pairgate SDK.
