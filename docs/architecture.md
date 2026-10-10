# Architecture

Pairgate is a join ranker with a slow side and a fast side. The slow side refreshes features. The fast side only reads the cache, applies rules, and returns one rank or an ordinary-route order.

Reeforce sits beside it on a different clock. It reads an interval summary. It never sits on the join path.

## System context

```mermaid
flowchart TB
  subgraph slow["Slow side — seconds to hours"]
    Night[Nightly resource snapshot]
    Hist[Historical contact profile]
    Path[Pre-queue attribute capture]
  end

  subgraph fast["Fast side — one join"]
    Cache[(Feature cache)]
    Rules[Rules layer]
    Rank[Ranker]
    Guard[Wait guard]
  end

  Router[Routing engine]
  Reeforce[Reeforce gap and delta]

  Night --> Cache
  Hist --> Cache
  Path --> Cache
  Router -->|contact arrived or person free| Rules
  Cache --> Rules
  Rules --> Guard
  Guard --> Rank
  Rank -->|join or ordinary route| Router
  Rank --> Summary[Interval summary]
  Guard --> Summary
  Summary --> Reeforce
  Reeforce -->|schedule edit, off the join path| Router
```

The routing engine remains the system of record for who is in which state. Pairgate does not own agent state. It consumes a live view of availability and wait, ranks, and returns a decision the engine can apply. Extracting state out, deciding, and pushing the decision back through a slow event stream is the failure mode this design refuses: a late decision is applied to a pool that has already changed, and the next decision is wrong because the first one was late.

## Components

```mermaid
flowchart LR
  subgraph pairgate["Pairgate"]
    Elig[Eligibility]
    Cohort[Cohort assignment]
    Guard[Wait guard]
    Rank[Ranker]
    Cache[(Cache)]
    Pub[Summary publisher]
  end

  Elig --> Cohort --> Guard --> Rank
  Cache --> Rank
  Cache --> Guard
  Rank --> Pub
  Guard --> Pub
```

| Component | Responsibility | Not responsible for |
|-----------|----------------|---------------------|
| Eligibility | Call-type and line-of-work allow list. A small exclusion set, not a second policy language. | Model weights |
| Cohort assignment | Sticky matched vs control flag for measurement | Changing the objective |
| Wait guard | Breach test from the live wait distribution | Ranking |
| Ranker | Score candidates for one anchor | Holding contact profiles outside the cache |
| Cache | Serve the four feature sets at decision time | Training |
| Summary publisher | Aggregate the interval for Reeforce | Proposing `MOVE_MEAL` |

Intended modules, when code lands:

| Module | Role |
|--------|------|
| `pairgate-model` | Rank request, rank result, interval summary |
| `pairgate-rules` | Eligibility, cohort, guard |
| `pairgate-rank` | Score function and candidate cap |
| `pairgate-summary` | Roll the interval into the Reeforce contract |

## Two clocks

```mermaid
sequenceDiagram
  participant Path as Pre-queue capture
  participant Cache
  participant Router as Routing engine
  participant PG as Pairgate
  participant RF as Reeforce

  Note over Path,Cache: Before the contact is transferred
  Path->>Cache: write contact-path features
  Note over Router,PG: The join. Budget under 150 ms
  Router->>PG: rank request
  PG->>Cache: read features and live state
  PG-->>Router: join or ordinary route
  Note over PG,RF: After the interval closes
  PG->>RF: interval summary
  RF-->>Router: schedule edit for a later interval
```

Schedule edits apply to a future interval. They are not a way to fix a join that is already late.

## Feature cache

```mermaid
flowchart TB
  subgraph refresh["Refresh"]
    R1[Resource features<br/>nightly]
    R2[Contact features<br/>loaded before handoff]
    R3[Path features<br/>written before transfer]
    R4[Live state<br/>availability and wait]
  end
  Cache[(Decision cache)]
  R1 --> Cache
  R2 --> Cache
  R3 --> Cache
  R4 --> Cache
  Cache --> Decision[Rank request reads only this box]
```

If a resource has no feature row, the rules layer takes the documented fallback (treat as ordinary route for that candidate, or for the decision, according to line-of-work policy). The ranker does not block on a fetch.

## What crosses the Reeforce boundary

```mermaid
flowchart LR
  subgraph allowed["Crosses"]
    S[Scarce cohort counts]
    B[Breach rate and wait moments]
    C[Resource coverage scores]
  end
  subgraph refused["Does not cross"]
    P[Contact profiles]
    W[Model weights]
    Q[Per-contact ranks]
  end
  allowed --> RF[Reeforce delta score]
```

Reeforce already knows the roster id. `resourceCoverage[].resourceId` uses that id so a `MOVE_MEAL` can name the same person the gap board names. See [reeforce-contract.md](reeforce-contract.md).

## Deployment shape

The ranker, the rules layer, and the cache client run in one process next to the routing engine's decision point. Training, nightly snapshots, and the interval publisher run elsewhere. Adding a remote call to the rank path requires a latency note; see [latency.md](latency.md).
