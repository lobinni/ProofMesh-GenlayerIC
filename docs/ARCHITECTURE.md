# Architecture

ProofMesh is a single-file Intelligent Contract built around one
principle: keep every deterministic layer on-chain and unforgiving, and
confine subjectivity to one small, heavily validated consensus block.

```
┌────────────────────────────────────────────────────────────────┐
│ deterministic on every node (no consensus needed)              │
│                                                                │
│  register_source ─ URL canonicalization, fingerprints          │
│  create_claim ─ definition validation, sorted commitments      │
│  void_claim ─ creator-only terminal cancellation               │
│  aggregation ─ union-find, consistency check, verdict,         │
│                result fingerprint                              │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│ subjective (leader/validator exchange, gl.vm.run_nondet)       │
│                                                                │
│  bounded web snapshots  ─  gl.nondet.web.request + render      │
│  semantic classification ─ gl.nondet.exec_prompt (json)        │
│  exact-schema validation, availability enforcement             │
│  validator independently re-derives and compares projections   │
└────────────────────────────────────────────────────────────────┘
```

## Four layers

### 1. Commitment

`register_source(source_id, url, expected_hash)` canonicalizes an HTTPS
URL, validates an optional SHA-256 commitment of the expected rendered
text, records the creator, and writes a deterministic fingerprint:

```
sha256( json([ "PROOFMESH-SOURCE-DEFINITION-V1",
               { source_id, creator, url, expected_hash } ]) )
```

URL identity is **host-canonical but path-preserving**: the scheme is
lower-cased to `https`, the hostname is IDNA-encoded and lower-cased,
explicit port 443 is removed, but path and query spelling is preserved.
`/a/../b` is not normalized to `/b` and percent escapes are not decoded —
so two differently spelled paths are two different sources on purpose.

### 2. Claim definition

`create_claim(claim_id, statement, criteria, source_ids,
required_support_groups)` validates all inputs, requires every referenced
source to be COMMITTED, sorts and deduplicates the source list before
persistence (so equivalent input orders produce the same definition), and
bounds the threshold to `1..len(source_ids)`. The claim is immutable from
that point: the only remaining transitions are `assess` (once) and
`void_claim` (creator, pre-assessment).

### 3. Semantic consensus

`assess(claim_id)` copies the claim definition and source commitments to
memory, then runs one `gl.vm.run_nondet(leader_fn, validator_fn)`
exchange.

The **leader**:

1. Builds a snapshot for every committed source: preflight `web.request`
   must return a 2xx status; `web.render` text must be non-empty, ≤
   32,768 chars, within the 65,536-char aggregate budget, and must match
   the committed `expected_hash` when present. Any failure marks the
   source *unavailable*.
2. Prompts the model with statement, criteria, available texts (wrapped
   in begin/end sentinels and declared untrusted), the unavailable id
   list, and the exact pair list to classify.
3. Validates the response against the exact schema
   (`_validate_graph_result`) and returns `{ graph, unavailable }`.

The **validator** independently re-fetches, re-prompts, and re-validates
with the same code, then:

- rejects if its own derivation fails any schema rule;
- rejects if its unavailable set differs from the leader's (a snapshot
  agreement check — flaky fetches fail consensus rather than guessing);
- rejects unless the leader's graph and its own agree on the **equality
  projection**: every `(source_id, position)` and every ordered
  `(left_id, right_id, relation)`. Free-form reasoning is persisted but
  deliberately excluded from the projection, so validators with
  equivalent judgments but different prose still reach consensus.

Availability is enforced **deterministically**, not trusted to the model:
an unavailable source must be classified `UNRESOLVED` or validation
fails. The model can never upgrade a failed fetch into support.

### 4. Deterministic aggregation

After consensus returns, the contract re-validates the payload
deterministically, reduces the graph with union-find, and applies the
verdict rules (see [VERDICT_RULES.md](VERDICT_RULES.md)). Only then are
positions, relations, groups, reasoning, and a result fingerprint
written — one write, at the end. Any failure earlier in the pipeline
leaves the claim in `READY` with nothing persisted.

## Storage layout

| Field | Type | Contents |
| --- | --- | --- |
| `sources` | `TreeMap[str, SourceRecord]` | id → committed source |
| `source_urls` | `TreeMap[str, str]` | canonical URL → id (uniqueness) |
| `claims` | `TreeMap[str, ClaimRecord]` | id → claim definition + settled aggregate |
| `owner_sources` | `TreeMap[str, str]` | owner hex → JSON sorted id list (≤128) |
| `owner_claims` | `TreeMap[str, str]` | owner hex → JSON sorted id list (≤128) |

Claim records store JSON payloads (`source_ids_json`, `positions_json`,
`relations_json`, `groups_json`) so the settled graph round-trips exactly
through storage and views return parsed structures.

## Why these bounds

- 8 sources → 28 pairs keeps the prompt and the stored graph small and
  verification cheap on every validator.
- 32 KiB per snapshot / 64 KiB aggregate caps nondeterministic work and
  prompt size while covering typical articles and reports.
- 128-record owner indexes make per-wallet discovery feasible without an
  unbounded on-chain enumeration.
- One-shot assessment (`READY → SETTLED`) removes dispute/retry state
  machines; a failed assessment simply never writes, and the claim can be
  retried by building a new claim over the same committed sources.

## Failure model

| Failure | Effect |
| --- | --- |
| fetch exception / non-2xx preflight | source unavailable → position forced `UNRESOLVED` |
| empty / oversized / aggregate overflow | same |
| expected-hash mismatch | same |
| model emits malformed JSON | leader validation error → transaction reverts, claim stays `READY` |
| schema violation (missing pair, dup edge, bad enum, …) | same |
| leader/validator projections diverge | validator rejects → consensus fails → claim stays `READY` |
| leader/validator snapshots diverge | same |
| contradictory pair relations | consistent aggregation → `UNRESOLVED` verdict |

Two design notes:

- **Conservatism**: every ambiguity path resolves toward fewer
  independent groups, an `UNRESOLVED` source, or an `UNRESOLVED` verdict.
  Nothing in the contract converts uncertainty into support.
- **Atomicity**: verdict computation runs after consensus, not inside it,
  so aggregating is byte-identical on every node and cannot be a source
  of forks.
