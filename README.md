# ProofMesh

**How many genuinely independent sources actually back this claim?**

ProofMesh is a bounded GenLayer Intelligent Contract for evidence
attestation. Five URLs can still be a single original voice when four of
them are syndicated copies, derived reports, or repetitions of the same
upstream statement — so ProofMesh counts *independent source groups*, not
raw URLs, and finalizes one verdict under multi-validator consensus.

The repository is **contract-first**: it contains the Intelligent
Contract, a complete Direct Mode test suite, optional live-network
integration tests, documentation, and ready-to-run samples. There is no
frontend and no deployment lock-in; any UI can connect through the public
read/write interface documented below.

## Verified deployment

**DEPLOYED: YES — GenLayer Studionet**

| Field | Value |
| --- | --- |
| Network | GenLayer Studionet |
| Chain ID | `61999` |
| RPC | `https://studio.genlayer.com/api` |
| Contract address | `0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F` |
| Explorer | [address page](https://explorer-studio.genlayer.com/address/0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F) |
| Schema | `proofmesh.v1` — 10 methods (4 writes, 6 views) |
| Deployed via | GenLayer Studio (`studio.genlayer.com`) |
| Source SHA-256 | `cdeea1a13ba05564ebd84011242e07d7f673b6612cab7b515213cf66391c6cb9` |

This deployment was published from the current source in this repository,
which declares the contract in the canonical GenVM form
(`from genlayer import *`, direct `gl.Contract` inheritance, explicit
`__init__`) so the E1xx schema-validation gates pass (review finding
E106 resolved). An earlier superseded deployment is recorded in
[deployments.json](deployments.json) for audit history.

Zero-funding verification from your machine (read-only, no wallet
required):

```bash
pip install genlayer-py
python samples/query_live.py
```

The script asserts the live contract's schema version, bounds, and enums
against this source tree. Machine-readable deployment facts live in
[deployments.json](deployments.json).

## Lifecycle at a glance

```
register_source  ──▶  COMMITTED source (canonical URL, fingerprint)
create_claim     ──▶  READY claim (immutable definition, sorted sources)
                        │
             ┌──────────┴──────────┐
             ▼                     ▼
        assess (once)          void_claim (creator only)
             │                     │
             ▼                     ▼
   SETTLED + final verdict        VOID  (terminal)
```

Assessment fetches a bounded text snapshot of every committed source,
classifies each source (`SUPPORTS` / `REFUTES` / `NEUTRAL` / `UNRESOLVED`)
and every available pair (`INDEPENDENT` / `DERIVED` / `SAME_ORIGIN` /
`UNCLEAR`) inside one leader/validator exchange, then deterministically
reduces the pair graph to independent groups and a final verdict:

| Verdict        | Meaning                                                        |
| -------------- | -------------------------------------------------------------- |
| `ATTESTED`     | ≥ `required_support_groups` independent supporting groups, no refuting group |
| `DISPUTED`     | At least one supporting group **and** at least one refuting group |
| `INSUFFICIENT` | Independent support below threshold (refutation alone lands here too) |
| `UNRESOLVED`   | Any unresolved source, an inconsistent graph, or a mixed-stance group |

`DERIVED`, `SAME_ORIGIN`, and `UNCLEAR` edges merge sources into one group
transitively. `UNCLEAR` is deliberately conservative: uncertainty never
grants independence. An explicit `INDEPENDENT` edge inside an already
joined component makes the graph inconsistent and resolves `UNRESOLVED`.
Full rules: [docs/VERDICT_RULES.md](docs/VERDICT_RULES.md).

## Repository layout

```
contracts/
  proof_mesh.py            # the Intelligent Contract (single file)
tests/
  direct/                  # fast in-memory tests (~ms each, mocked web/LLM)
    conftest.py
    test_registration.py
    test_claim_lifecycle.py
    test_assessment.py
    test_assessment_edges.py
    test_validator_consensus.py
  integration/             # live-network smoke tests (opt-in)
    test_studio_smoke.py
samples/
  query_live.py            # read-only verification of the live deployment
  studio_walkthrough.md    # click-by-click Studio manual test script
  payloads/                # copy-paste call arguments for Studio
  cli_demo.py              # end-to-end demo via the genlayer-py SDK
docs/
  ARCHITECTURE.md          # layers, storage, consensus design
  VERDICT_RULES.md         # grouping and verdict semantics in full
  TESTING.md               # direct tests, lint gates, CI notes
  DEPLOYMENT.md            # Studio / CLI / SDK deployment paths
deployments.json           # machine-readable deployment facts
gltest.config.yaml         # networks for integration tests
pyproject.toml             # pytest / pyright configuration
requirements.txt           # pinned toolchain
```

## Quick start (5 minutes)

Requires Python ≥ 3.12.

```bash
cd proofmesh
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Fast unit tests: ~75 tests, milliseconds each, no network needed.
pytest tests/direct -v
```

Lint gates before deployment:

```bash
genvm-lint check contracts/proof_mesh.py
genvm-lint validate --json contracts/proof_mesh.py
genvm-lint schema --json contracts/proof_mesh.py
```

Optional live-network integration smoke tests (Studio or studionet):

```bash
PROOFMESH_INTEGRATION=1 gltest tests/integration/ -v -s
```

Deployment paths (Studio UI, CLI, SDK) are documented in
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md), and a click-by-click manual test
script lives in [samples/studio_walkthrough.md](samples/studio_walkthrough.md).

## Public interface

Writes:

| Method | Returns | Notes |
| --- | --- | --- |
| `register_source(source_id, url, expected_hash)` | `str` fingerprint | Canonicalizes the HTTPS URL; optional SHA-256 commitment of the rendered text |
| `create_claim(claim_id, statement, criteria, source_ids, required_support_groups)` | `str` fingerprint | 1–8 committed sources; IDs sorted and deduplicated |
| `void_claim(claim_id)` | `VOID` | Creator only, READY only, terminal |
| `assess(claim_id)` | result dict | One-shot; READY → SETTLED under consensus |

Views:

| Method | Returns |
| --- | --- |
| `get_source(source_id)` | source record dict |
| `get_claim(claim_id)` | full claim dict incl. verdict, positions, relations, groups, fingerprints |
| `get_claim_fingerprint(claim_id)` | SHA-256 definition fingerprint |
| `get_owner_source_ids(owner)` | sorted, bounded per-owner index (≤128) |
| `get_owner_claim_ids(owner)` | sorted, bounded per-owner index (≤128) |
| `get_protocol_info()` | schema version, bounds, enums — for SDK builders |

## Bounds

- ≤ 8 sources per claim → ≤ 28 pairwise relations
- ≤ 32,768 fetched characters per source; ≤ 65,536 in aggregate
- Statement ≤ 8,000 chars, criteria ≤ 4,000, reasoning ≤ 2,000
- Identifiers: ≤ 96 ASCII letters/digits/`.`/`_`/`-`
- Owner indexes capped at 128 records each

Any fetch failure, non-2xx preflight response, oversized or empty
snapshot, aggregate overflow, or expected-hash mismatch marks only the
affected source `UNRESOLVED` — it can never silently become support.

## Trust model and limitations

- Semantic classification is an LLM-backed interpretation of bounded
  rendered text under validator consensus, not cryptographic proof of
  origin or truth. The prompt treats fetched text as untrusted data,
  forbids embedded instructions and outside facts, and requires
  `UNRESOLVED`/`UNCLEAR` when classification is unreliable.
- Only the final aggregate is written; failed consensus or failed schema
  validation cannot partially assess a claim.
- Assessment is open to any caller (public utility); ownership indexes
  provide attribution and discovery, not access control. `void_claim` is
  the exception: only the claim creator may void, and only before
  assessment.
- The contract commits expected hashes but does not archive page content
  on-chain.

## Last update

| Date (UTC) | Update |
| --- | --- |
| **2026-10-19** | E106-hardening release and redeploy. The contract header now uses the canonical `from genlayer import *` form with direct `gl.Contract` inheritance and an explicit `__init__`, satisfying static GenVM schema validation (review finding E106). Redeployed on Studionet at [`0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F`](https://explorer-studio.genlayer.com/address/0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F) from the current source (`sha256: cdeea1a1…c6cb9`); the earlier `0x8b29…E5eB955` deployment is recorded as superseded in [deployments.json](deployments.json). Same release: `LICENSE` (MIT), GitHub Actions CI (`genvm-lint` gates + direct tests), edge-case test suite, `samples/query_live.py`, and full documentation sync. |

Earlier history: initial contract, Direct Mode suite, and the first
Studionet deployment preceded this entry; see git history for the full
timeline.

## License

MIT
