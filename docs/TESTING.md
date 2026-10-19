# Testing guide

ProofMesh ships three layers of tests — fast Direct Mode unit tests, a
Direct Mode validator-consensus suite, and opt-in live-network smoke
tests — plus a read-only check against the verified live deployment. This
guide explains what each layer proves and how to run it.

## 0. Verify the live deployment (read-only, zero funding)

The repository records a verified Studionet deployment in
`deployments.json`
(`0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F`). Validate it from your
machine without a funded wallet:

```bash
pip install genlayer-py
python samples/query_live.py
```

The script fails loudly on any schema, bounds, or enum mismatch. Write
paths on the live contract are exercised by
[../samples/cli_demo.py](../samples/cli_demo.py) (needs a funded Studio
account) or by the manual checklist in
[../samples/studio_walkthrough.md](../samples/studio_walkthrough.md).

## 1. Direct Mode unit tests (default)

Direct mode runs the contract in memory. The web and LLM boundaries are
mocked; **every deterministic layer executes for real** —
canonicalization, validation, grouping, verdicts, fingerprints.

```bash
pip install -r requirements.txt
pytest tests/direct -v
```

Approximately 75 tests across five files, milliseconds each, no network.

### What is covered

| File | Scope |
| --- | --- |
| `test_registration.py` | fingerprints, duplicate id/URL rejection, identifier rules (incl. confusables), IDNA/port/IP canonicalization, hash validation, per-owner sorted indexes, 128-record index cap |
| `test_claim_lifecycle.py` | claim fingerprints, sorted/deduped source lists, threshold bounds, statement/criteria limits, duplicate claims, claim indexes, `void_claim` lifecycle, `get_protocol_info`, atomicity when the nondet boundary has no mocks |
| `test_assessment.py` | all four verdicts, every grouping rule, inconsistency, mixed-stance groups, one-shot enforcement, all schema gates (missing/duplicate/reverse/self edges, bad enums, missing/unknown positions, extra keys, reasoning bounds, malformed JSON), fetch failure modes (non-2xx, oversized, empty, hash mismatch), deterministic result fingerprints |
| `test_assessment_edges.py` | permissionless assessment, cross-owner source references, aggregate budget overflow, exact per-source size fit, canonical normalization of scrambled relation payloads |
| `test_validator_consensus.py` | `run_validator()` acceptance for honest leaders, rejection on divergent semantic projections, rejection on snapshot-availability divergence, rejection when the validator's own derivation fails schema validation |

### Writing new tests

Helpers live in `tests/direct/conftest.py`:

```python
from conftest import deploy, register, open_claim, setup_claim, settle, semantic_result

def test_something(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}),
    )
    assert result["verdict"] == "ATTESTED"
```

- `semantic_result(positions, relations=None)` builds a schema-valid
  payload; relations default to `INDEPENDENT` for every available pair.
- `settle(...)` wires web mocks (per-source bodies; a dict sets
  `status`/`body`, `None` simulates a fetch failure) and the LLM mock
  matched on the prompt marker `SEMANTIC_TASK_V1`, then calls `assess`.
- Use `direct_vm.expect_revert(...)` around calls that must fail and
  re-assert that the claim stayed `READY` (atomicity pattern).

### Validator consensus tests

When the write method runs, direct mode executes the leader function and
captures the validator closure. Swap the mocks, then call
`direct_vm.run_validator()` to check whether a real validator would have
accepted the leader's proposal. See `test_validator_consensus.py` for the
pattern; it is the fastest way to prove that consensus — not just the
leader — enforces availability agreement.

### Mock formats

```python
direct_vm.mock_web(r"reports\.example\.org/a", {"status": 200, "body": "text"})
direct_vm.mock_web(re.escape(url), {"status": 500, "body": "boom"})
direct_vm.mock_llm("SEMANTIC_TASK_V1", json.dumps(payload))
direct_vm.clear_mocks()
```

## 2. Lint and schema gates

Run these before every deployment — they are the same GenVM contract-shape
and schema checks the reviewer's validation runs (including E106):

```bash
genvm-lint check contracts/proof_mesh.py
genvm-lint validate --json contracts/proof_mesh.py
genvm-lint schema --json contracts/proof_mesh.py
```

Expected schema surface: 10 methods — 4 writes (`register_source`,
`create_claim`, `void_claim`, `assess`) and 6 views (`get_source`,
`get_claim`, `get_claim_fingerprint`, `get_owner_source_ids`,
`get_owner_claim_ids`, `get_protocol_info`).

Optional static typecheck (GenVM-aware):

```bash
genvm-lint typecheck contracts/proof_mesh.py
```

If `genvm-lint schema` fails with an import error about a legacy module
layout on newer toolchains, upgrade with
`pip install -U genvm-linter genlayer-test`; the contract header
(`# { "Depends": "py-genlayer:test" }`) is intentionally unpinned so the
current network runtime is used.

A note on earlier revisions: this contract previously declared its base
class through a try/except import alias (`_contract_base`), which static
GenVM validation could not resolve and reported as E106. The header now
uses the canonical `from genlayer import *` form with
`class ProofMesh(gl.Contract):` and an explicit `__init__`, the exact
declaration shape every official example uses — keep it that way.

## 3. Live-network smoke tests (opt-in)

`tests/integration/test_studio_smoke.py` deploys the contract to the
network configured in `gltest.config.yaml` and runs the full flow with
real web fetches and real model consensus:

```bash
PROOFMESH_INTEGRATION=1 gltest tests/integration/ -v -s
```

- Skipped by default (needs Studio/studionet running and takes minutes).
- Asserts finalization invariants only: valid verdict enum, bounded
  groups, 64-hex result fingerprint. The concrete verdict of live pages
  is intentionally not pinned.
- With `--leader-only`, consensus is skipped (faster iteration, weaker
  guarantee).

## Suggested CI shape

1. `genvm-lint check contracts/proof_mesh.py`
2. `genvm-lint schema --json contracts/proof_mesh.py` and assert the
   method set equals the expected 10-method surface.
3. `pytest tests/direct -q`
4. Nightly only: `PROOFMESH_INTEGRATION=1 gltest tests/integration/ -v -s`
   against a disposable Studio instance.

## Debugging tips

- A reverted `assess` must always leave `get_claim(...)["state"]`
  equal to `READY`; every failure-mode test asserts this. If you see a
  `SETTLED` claim after a revert, the last write in `assess` moved
  before a failing gate.
- Fingerprint mismatches in tests are almost always signature drift:
  recompute the expected digest with the same canonical JSON rules
  (`sort_keys`, compact separators, `ensure_ascii=False`).
- If web mocks seem ignored, make sure your pattern matches the
  **canonicalized** URL (the contract canonicalizes before fetching).
