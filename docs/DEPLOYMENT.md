# Deployment guide

## Current live deployment

| Field | Value |
| --- | --- |
| Network | GenLayer Studionet |
| Chain ID | `61999` |
| RPC | `https://studio.genlayer.com/api` |
| Contract address | `0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F` |
| Explorer | https://explorer-studio.genlayer.com/address/0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F |
| Deployed via | GenLayer Studio |
| Source SHA-256 | `cdeea1a13ba05564ebd84011242e07d7f673b6612cab7b515213cf66391c6cb9` |
| Read-only check | `python samples/query_live.py` |

Deployed from the current E106-compliant source in this repository. The
superseded earlier deployment (`0x8b29…E5eB955`, pre-refactor header) is
kept in [../deployments.json](../deployments.json) under
`previous_deployments` for audit history. Everything below explains how
to reproduce an equivalent deployment.

ProofMesh has no constructor arguments and no deployment configuration —
deploying means publishing `contracts/proof_mesh.py` to a GenLayer
network.

### GenVM schema-validation compliance (E106)

GenVM contract-shape validation requires the canonical declaration form,
which this contract follows exactly:

1. **Canonical import** — a single `from genlayer import *` exports the
   `gl` namespace (`gl.Contract`), `TreeMap`, `Address`, `u256`, and
   `@allow_storage` in every SDK layout. Do not route the contract base
   class through a dynamic alias (`_contract_base = ...` inside
   try/except import fallbacks): static validators cannot resolve it,
   and the schema check reports `E106 (__init__ is absent)` even when a
   constructor exists.
2. **Direct inheritance** — `class ProofMesh(gl.Contract):`.
3. **Explicit constructor** — an `__init__` declared directly on the
   contract class (an empty body is fine; all persistent state lives in
   TreeMaps and starts empty).

Three supported deployment paths follow. Before any of them, run the
gates from [TESTING.md](TESTING.md).

```bash
genvm-lint check contracts/proof_mesh.py
genvm-lint schema --json contracts/proof_mesh.py
pytest tests/direct -q
```

## Path A — GenLayer Studio (manual)

1. Open https://studio.genlayer.com and start a local Studio instance
   (Docker) or connect to a hosted network.
2. Create or import a wallet in the Studio UI; the deployer becomes an
   ordinary user of the contract — ProofMesh has no owner privileges.
3. **Contracts → Deploy** and upload/paste the full contents of
   `contracts/proof_mesh.py`.
4. Confirm the deployment and wait for the transaction to finalize.
5. Note the contract address, then continue with
   [../samples/studio_walkthrough.md](../samples/studio_walkthrough.md)
   for a full manual test of every method.

The Studio validator nodes execute a real leader/validator exchange for
`assess`, so expect assessment transactions to take minutes, not seconds.

## Path B — GenLayer CLI

```bash
pip install genlayer-cli   # or your environment's package name
genlayer network set studionet
genlayer deploy --contract contracts/proof_mesh.py
```

The CLI prints the deployment transaction hash and the resulting contract
address. `ProofMesh.__init__` takes no arguments, so no `--args` flag is
needed.

Useful follow-ups:

```bash
genlayer call <address> get_protocol_info
genlayer send <address> register_source '["src-1", "https://example.com/", ""]' --account <you>
```

## Path C — Python SDK (`genlayer-py`)

`samples/cli_demo.py` implements the full register → claim → assess loop
with receipt polling. The essential calls:

```python
from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

account = create_account()                # or from an existing key
client = create_client(chain=studionet, account=account)

tx = client.write_contract(
    account=account,
    address=contract_address,
    function_name="register_source",
    args=["src-1", "https://example.com/", ""],
    value=0,
)
receipt = client.wait_for_transaction_receipt(
    transaction_hash=tx,
    status=TransactionStatus.FINALIZED,
)

record = client.read_contract(
    address=contract_address,
    function_name="get_source",
    args=["src-1"],
)
```

## After deployment: verification checklist

1. **Readback** — `get_protocol_info()` returns
   `{"schema": "proofmesh.v1", ...}` with the documented bounds.
2. **Smoke register** — `register_source` with a real HTTPS URL, then
   `get_source` returns status `COMMITTED` and a 64-hex fingerprint.
3. **Fingerprint check** — recompute the expected fingerprint with the
   canonical JSON rules and compare; mismatch means signature drift in
   your caller, not in the contract.
4. **Smoke claim + assess** — one claim over two public URLs, call
   `assess`, wait for finalization, then `get_claim` returns
   `state: SETTLED` with one of the four valid verdicts.
5. **Record the facts** — keep the network, chain id, RPC, contract
   address, deployment transaction hash, and ideally the source file's
   SHA-256 alongside the deployment so others can verify what they are
   calling:

   ```bash
   shasum -a 256 contracts/proof_mesh.py
   ```

## Publication checklist (source ↔ deployment evidence)

Use this when submitting the project for review so the submitted source
and the deployment evidence provably match:

1. Freeze the exact source file and compute its digest:
   `shasum -a 256 contracts/proof_mesh.py`.
2. Deploy **that exact file** (any uncommitted edit after step 1 changes
   the digest and invalidates the match).
3. Wait for **Finalized · Accepted** and record: network, chain id, RPC,
   contract address, deployment transaction hash, explorer link.
4. Fill every field of the matching entry in `deployments.json`
   and rerun `python samples/query_live.py --contract <new address>`.
5. Include in the submission: the source tree, `deployments.json`, the
   deployment transaction hash, and the explorer link.

If a reviewed deployment is superseded by a corrected source, deploy the
current file again, move the old entry to a `previous_deployments`
section, and update the top-level README address in the same commit as
the new evidence.

## Network notes

- State persists per deployment; there are no upgrade hooks, migrations,
  or admin keys. Redeploy to move.
- Assessment performs live HTTPS fetches from validator nodes. Target
  pages must be reachable from the validators' network, respond 2xx, and
  render useful text under 32 KiB for a source to be *available*.
- If Studio Dev RPCs are congested, writes can time out at submission;
  retry the same call. Reads are unaffected.
