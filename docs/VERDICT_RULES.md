# Verdict rules

This document is the complete semantic contract of ProofMesh: positions,
relations, grouping, consistency, and the four final verdicts. Every rule
below is deterministic — the model only proposes positions and relations;
these rules turn them into a verdict.

## Positions (per source)

| Position | Meaning |
| --- | --- |
| `SUPPORTS` | The source text substantiates the claim under the criteria |
| `REFUTES`  | The source text contradicts the claim under the criteria |
| `NEUTRAL`  | Relevant, but neither supports nor refutes |
| `UNRESOLVED` | Missing, unreadable, irrelevant, or ambiguous text — **including every source whose snapshot fetch failed** |

## Relations (per pair of available sources)

For `n` available (non-`UNRESOLVED`) sources, the schema requires exactly
`n * (n - 1) / 2` relation edges — one for every pair, no more, no less.
Edges are stored with `left_id < right_id`; duplicates, reverse
duplicates, and self-edges are validation errors.

| Relation | Group effect |
| --- | --- |
| `INDEPENDENT` | Keeps the two sources in separate groups |
| `DERIVED` | Joins the groups (one restates/reports the other) |
| `SAME_ORIGIN` | Joins the groups (same publisher, wire copy, upstream statement) |
| `UNCLEAR` | Joins the groups — **conservative**: uncertainty never grants independence |

## Grouping

Union-find over the available sources:

1. Start: every available source is its own component.
2. For every edge with relation `DERIVED`, `SAME_ORIGIN`, or `UNCLEAR`,
   union the endpoints (transitively).
3. The resulting components are the **independence groups**, stored
   sorted (members sorted, groups sorted by first member) so the stored
   artifact is byte-deterministic.

Five URLs can be one voice: a chain of `DERIVED` edges collapses all of
them into a single group that counts once.

## Consistency

After all joins, check every explicit `INDEPENDENT` edge:

- If both endpoints ended in the same component, the pairwise
  classifications contradict each other. The graph is **inconsistent**
  and the verdict is `UNRESOLVED` — the independence claim is never
  silently ignored.

Example: `a-b: SAME_ORIGIN`, `b-c: SAME_ORIGIN`, `a-c: INDEPENDENT` joins
`{a,b,c}` and then fails consistency.

## Group stance

Within a group:

- any `SUPPORTS` member → the group is *supporting*
- any `REFUTES` member → the group is *refuting*
- both → the group contradicts itself → verdict `UNRESOLVED`
- all `NEUTRAL` → the group is neither (neutral never counts as support)

## Final verdict

Evaluated in this exact order:

1. **Any position `UNRESOLVED`** → `UNRESOLVED`.
2. **Graph inconsistent** → `UNRESOLVED`.
3. **Any group with both stances** → `UNRESOLVED`.
4. **≥ 1 supporting group and ≥ 1 refuting group** → `DISPUTED`.
5. **supporting groups ≥ `required_support_groups` and no refuting
   group** → `ATTESTED`.
6. Otherwise → `INSUFFICIENT`.

Corollaries worth remembering:

- Refutation alone is `INSUFFICIENT`, not `DISPUTED`: dispute requires at
  least one group on each side.
- `NEUTRAL` sources never help reach the threshold.
- A single available, independent `SUPPORTS` source can `ATTEST` a claim
  with `required_support_groups = 1`.
- A claim where *every* source failed to fetch is `UNRESOLVED`
  (rule 1), never `INSUFFICIENT`.

## Worked examples

All examples use `required_support_groups = 2`.

| Sources and relations | Groups | Verdict |
| --- | --- | --- |
| a,b,c,d all SUPPORTS, all pairs INDEPENDENT | 4 | `ATTESTED` (4 ≥ 2) |
| a,b,c,d all SUPPORTS, a-b `SAME_ORIGIN`, c-d `DERIVED` | 2 | `ATTESTED` (2 ≥ 2) |
| a,b,c,d all SUPPORTS, a-b `SAME_ORIGIN`, c-d `DERIVED`, threshold 3 | 2 | `INSUFFICIENT` (2 < 3) |
| a SUPPORTS, b SUPPORTS, a-b `UNCLEAR` | 1 | `INSUFFICIENT` (conservative merge) |
| a SUPPORTS, b REFUTES, INDEPENDENT | 2 | `DISPUTED` |
| a REFUTES, b REFUTES, INDEPENDENT | 2 | `INSUFFICIENT` |
| a SUPPORTS, b REFUTES, a-b `SAME_ORIGIN` | 1 | `UNRESOLVED` (mixed stance) |
| a SUPPORTS, b fetch failed | 1 (+b excluded) | `UNRESOLVED` (rule 1) |
| a,b,c SUPPORTS, a-b + b-c `SAME_ORIGIN`, a-c `INDEPENDENT` | 1 | `UNRESOLVED` (inconsistency) |
| a,b NEUTRAL | 2 | `INSUFFICIENT` |

## Persistence

The settled claim stores:

- `verdict` — one of the four verdicts
- `positions` — `[{"source_id", "position"}]` sorted by id
- `relations` — `[{"left_id", "right_id", "relation"}]` sorted by pair
- `groups` — the independence groups
- `graph_consistent`, `supporting_groups`, `refuting_groups`
- `reasoning` — the model's short prose (excluded from consensus
  equality, kept for inspection)
- `result_fingerprint` — `sha256` over the canonical tuple
  `[ "PROOFMESH-RESULT-V1", { claim_id, verdict, positions, relations,
  groups_payload, reasoning } ]`

Recomputing the fingerprint from a `get_claim` response verifies that the
stored aggregate was produced by exactly these rules from exactly these
inputs.
