# Studio walkthrough

A complete manual test of ProofMesh inside GenLayer Studio
(https://studio.genlayer.com). Each step names the method, gives the
exact arguments to paste, and states the expected result. Total time:
~15 minutes, mostly waiting for consensus finalization.

## 0. Deploy (or reuse the live one)

A verified deployment already exists on Studionet — you can execute every
step below against it instead of deploying your own copy:

- Address: `0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F`
- Explorer: https://explorer-studio.genlayer.com/address/0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F
- In Studio: **Contracts → Open existing** and paste that address.

To deploy your own instead:

1. Open Studio, select your network, and connect/fund a wallet.
2. Contracts → Deploy → paste the entire `contracts/proof_mesh.py`.
3. Wait until the deployment transaction is **Finalized**. Copy the
   contract address.

Sanity check: call the view `get_protocol_info` with no arguments.
Expected: a dict with `"schema": "proofmesh.v1"`, bounds
(`max_sources_per_claim: 8`), and the enum lists.

> **Using the shared live deployment?** Identifiers are single-use per
> contract. Prefix every `source_id` and `claim_id` below with something
> unique (for example `you<wallet-suffix>-src-iana`) so your run does not
> collide with other testers' registrations. Source URLs themselves are
> also single-use, so pick at least one URL nobody has committed yet.

## 1. Register sources (write)

Call `register_source` twice — from `samples/payloads/01_register_source.json`:

```json
{ "source_id": "src-iana", "url": "https://www.iana.org/domains/example", "expected_hash": "" }
```

```json
{ "source_id": "src-iana-managed", "url": "https://www.iana.org/domains", "expected_hash": "" }
```

Expected: each call returns a 64-character hex fingerprint once
finalized. Both appear via `get_source` with `status: "COMMITTED"`.

**Negative checks:**

- Repeat `register_source` with the same id → reverts
  (`source_id is already registered`).
- Same URL under a new id → reverts (`url is already registered`).
- `"url": "http://example.com"` → reverts (HTTPS only).

## 2. Discovery views

- `get_owner_source_ids` with your wallet address → both ids, sorted:
  `["src-iana", "src-iana-managed"]`.
- `get_source("src-iana")` → canonical URL unchanged (already lowercase),
  empty `expected_hash`, your lowercase hex `creator`.

## 3. Open a claim (write)

From `samples/payloads/02_create_claim.json`:

```json
{
  "claim_id": "claim-demo",
  "statement": "Example domains are reserved for use in documentation.",
  "criteria": "Support requires the page itself to state or demonstrate the documentation purpose of the domain. Mere mention is NEUTRAL.",
  "source_ids": ["src-iana", "src-iana-managed"],
  "required_support_groups": 1
}
```

Expected: a 64-hex claim fingerprint. `get_claim("claim-demo")` shows
`state: "READY"`, `source_ids: ["src-iana", "src-iana-managed"]`, and all
result fields `null`.

## 4. Assess (write, one-shot)

Call `assess` with `"claim-demo"`. This triggers real validator work —
web fetches plus model classification under leader/validator consensus —
so finalization takes minutes.

Expected `get_claim` after finalization:

- `state: "SETTLED"`
- `verdict` ∈ `ATTESTED / DISPUTED / INSUFFICIENT / UNRESOLVED`
  (typically `ATTESTED` for these two pages)
- `positions`: one entry per source with an enum position
- `relations`: the pairwise classification(s) — one edge for two sources
- `groups`: independence groups (e.g. `[["src-iana", "src-iana-managed"]]`
  if the model reads one as derived from the same registry, or two
  singletons)
- `result_fingerprint`: 64-hex digest

**One-shot check:** call `assess("claim-demo")` again → reverts
(`claim is not ready for assessment.`).

## 5. Void lifecycle (write)

1. Create a second claim, `claim-void`, over the same sources.
2. Call `void_claim("claim-void")` → returns `VOID`;
   `get_claim` shows `state: "VOID"`.
3. `assess("claim-void")` → reverts (`not ready`).
4. Re-register `claim-void`? Claim ids are single-use; use a new id.

**Access control check:** with a second wallet, try
`void_claim` on a READY claim created by the first wallet → reverts
(`only the claim creator can void the claim.`).

## 6. Failure drills (optional)

| Drill | Expected |
| --- | --- |
| Register `https://httpstat.us/500` as `src-down`, claim it with a healthy source, assess | downgraded source becomes `UNRESOLVED`; verdict `UNRESOLVED` |
| `register_source` with `expected_hash` of different text, then assess | hash mismatch → `UNRESOLVED` |
| Two redundant sources (syndicated copies of one article) + threshold 2 | one group → `INSUFFICIENT` — the core proposition of ProofMesh |
| `create_claim` with 9 sources | reverts (`between 1 and 8`) |

## 7. Verify on your own machine

Pull the settled claim (`get_claim`) and recompute
`result_fingerprint` with the canonical JSON rules from
[../docs/VERDICT_RULES.md](../docs/VERDICT_RULES.md). A match proves the
stored aggregate followed exactly the documented grouping and verdict
semantics.
