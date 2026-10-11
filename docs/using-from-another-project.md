# Using Pairgate from another project

Another project does not import this repository. It speaks one of two open protocols, and it picks the protocol by what it is.

| Caller | Protocol | Why |
|--------|----------|-----|
| An assistant, an IDE, or a workflow that already has an MCP host | [Model Context Protocol](https://modelcontextprotocol.io/specification/2025-11-25) | The host lists tools and calls `rank_join` with a JSON schema. |
| Another agent that discovers peers and delegates tasks | [Agent2Agent](https://a2a-protocol.org) | The agent reads `/.well-known/agent-card.json` and sends a `SendMessage` task. |
| A scheduler on a slower clock | Either | It asks for the interval summary and decides its own schedule edit. |

The MCP arguments are the rank request. The A2A data part is that same request plus `skillId`, so the agent does not infer the task from prose. The example bodies are [examples/mcp-rank-call.json](../examples/mcp-rank-call.json) and [examples/a2a-rank-task.json](../examples/a2a-rank-task.json).

## What comes back from a rank

```json
{
  "decisionId": "d-1842",
  "disposition": "RANKED",
  "reason": "RANKED",
  "orderedCandidateIds": ["resource-22", "resource-14", "resource-7"],
  "scores": [
    { "candidateId": "resource-22", "score": 0.86 },
    { "candidateId": "resource-14", "score": 0.41 },
    { "candidateId": "resource-7", "score": 0.22 }
  ],
  "guardThresholdSeconds": 96.4
}
```

`ORDINARY` means the caller keeps its own rule (longest idle, next in line). Reasons are `INELIGIBLE`, `CONTROL`, `BREACH`, `EMPTY_POOL`, and `NO_SCORES`. A late result is discarded the same way. The caller does not retry the rank against a pool that has already changed.

## Where a model is allowed

The rank call above is arithmetic over a cache. A model participates in three other places, all off that call:

1. **Before the day, or before transfer.** It writes feature rows. The rank reads numbers already scaled to 0–1.
2. **Between intervals.** It proposes new weights from matched-versus-control outcomes. The proposal is not live until a person or a policy accepts it. The next score card is what a later rank reads.
3. **After the join.** A supervisor asks `explain-decision` (A2A) or `explain_decision` (MCP). A narrative may come from a model. It does not change the join.

A scheduling agent that wants a meal moved does not ask Pairgate to move it. It reads the interval summary (scarce cohorts, breach rate, coverage scores) and applies its own edit. That summary has no contact profiles and no weights.

## What to build next

The contracts and the baseline ranker are the seams. Useful follow-ups, each small enough for one pull request:

- An MCP server on stdio whose `tools/list` matches the published tool contract, and whose `rank_join` calls the baseline ranker.
- An A2A `SendMessage` handler for skill `rank-join` that returns the JSON above as a data-part artifact.
- A slow-side job that writes a score card only from an accepted weight proposal.
- A client in your own repository that sends [examples/mcp-rank-call.json](../examples/mcp-rank-call.json) and applies `orderedCandidateIds` only when `disposition` is `RANKED`.
