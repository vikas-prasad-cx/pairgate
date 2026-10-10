# Glossary

Terms Pairgate shares with Reeforce use the Reeforce meaning. See the [Reeforce glossary](https://github.com/vikas-prasad-cx/reeforce/blob/main/docs/glossary.md).

| Term | Meaning |
|------|---------|
| **Agent surplus** | More people are free than contacts are arriving. Rank people for the contact that just arrived. |
| **Contact surplus** | Contacts are waiting. Rank them for the person who just became free. |
| **Ordinary route** | Longest-idle or next-in-line. Used when matching is off, the contact is ineligible, the wait guard has fired, or the rank result is discarded. |
| **Out-of-sequence** | The join is the best rank, not the next in line. |
| **Anchor** | The single side being matched: the arriving contact, or the person who just became free. |
| **Candidate** | One member of the pool ranked against the anchor. |
| **Line of work** | A configuration of objective and weights. Different lines do not share one model by default. |
| **Eligibility** | Whether this contact type may be matched at all. |
| **Cohort** | `MATCHED` or `CONTROL`. Control skips ranking so outcome can be compared. |
| **Wait guard** | `mean(wait) + 2 × stdev(wait) + buffer`, after outliers are removed. Past the threshold, the contact takes the ordinary route. |
| **Breach** | A contact the wait guard removed from ranking. |
| **Coverage score** | How much of this interval's scarce arrivals a resource would rank first for. An input to Reeforce, not a join. |
| **Scarce cohort** | An arrival group whose capable available count is below the arrivals' share. |
| **Interval summary** | Aggregates published to Reeforce. No contact profiles, no weights. |
| **Join path** | The request that must finish inside the latency budget. |
| **Slow side** | Nightly snapshots, profile loads, and the interval publisher. |
