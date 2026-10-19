# Samples

Everything needed to exercise ProofMesh by hand against a live GenLayer
network, with no frontend required.

**Live deployment (Studionet):**
[`0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F`](https://explorer-studio.genlayer.com/address/0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F)
— RPC `https://studio.genlayer.com/api`, chain `61999`.

| Artifact | Purpose |
| --- | --- |
| [query_live.py](query_live.py) | Read-only verification of the live deployment (schema, bounds, enums) — no wallet funding needed |
| [studio_walkthrough.md](studio_walkthrough.md) | Click-by-click manual test script for GenLayer Studio covering every method and failure mode |
| [payloads/](payloads/) | Copy-paste call arguments for Studio's *Write Methods* panel |
| [cli_demo.py](cli_demo.py) | End-to-end scripted demo using the `genlayer-py` SDK (defaults to the live deployment) |

Start with the zero-funding check:

```bash
pip install genlayer-py
python samples/query_live.py
```

## The demo scenario

The payloads and the CLI demo use the same scenario:

> **Claim**: "Example domains are reserved for use in documentation."
>
> Sources: the IANA example-domain registry page and the IANA managed
> domains page — two pages that genuinely document the reservation.

Registering both, opening a claim with `required_support_groups = 1`, and
calling `assess` runs the complete pipeline: bounded snapshots, semantic
positions, pairwise provenance relations, group aggregation, and a
finalized verdict.

Expected outcome on a healthy network: `SETTLED` with a valid verdict —
usually `ATTESTED`, but the contract guarantees only the shape of the
result, not a specific model reading of live pages.

## Quick reference: method cheat sheet

| Step | Method | Arguments |
| --- | --- | --- |
| 1 | `register_source` | `"src-iana"`, `"https://www.iana.org/domains/example"`, `""` |
| 2 | `register_source` | `"src-iana-managed"`, `"https://www.iana.org/domains"`, `""` |
| 3 | `create_claim` | `"claim-demo"`, statement, criteria, `["src-iana", "src-iana-managed"]`, `1` |
| 4 | `assess` | `"claim-demo"` |
| 5 | `get_claim` | `"claim-demo"` |

For automated testing with mocked boundaries instead of a live network,
run the Direct Mode suite (`pytest tests/direct -v`) described in
[../docs/TESTING.md](../docs/TESTING.md).
