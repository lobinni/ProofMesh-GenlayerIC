#!/usr/bin/env python3
"""Read-only verification of the deployed ProofMesh contract.

Queries the live deployment on GenLayer Studionet and validates that the
schema version, bounds, and enums match this source tree. Read calls need
no wallet funding, so this is the fastest end-to-end sanity check after
(or before) your own deployment.

Usage:

    pip install genlayer-py
    python samples/query_live.py                     # default: the verified deployment
    python samples/query_live.py --contract 0xYour   # any other deployment
    python samples/query_live.py --claim claim-id    # also fetch one claim
    python samples/query_live.py --source source-id  # also fetch one source

Exits 0 on success, 1 on any mismatch or RPC failure.
"""

from __future__ import annotations

import argparse
import json
import sys

from genlayer_py import create_client
from genlayer_py.chains import studionet


DEFAULT_ADDRESS = "0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F"
EXPLORER = "https://explorer-studio.genlayer.com/address/"

EXPECTED_SCHEMA = "proofmesh.v1"
EXPECTED_BOUNDS = {
    "max_sources_per_claim": 8,
    "max_pairs_per_claim": 28,
    "max_fetched_content_per_source": 32768,
    "max_total_fetched_content": 65536,
    "max_owner_records": 128,
}
EXPECTED_VERDICTS = {"ATTESTED", "DISPUTED", "INSUFFICIENT", "UNRESOLVED"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", default=DEFAULT_ADDRESS)
    parser.add_argument("--claim", default=None)
    parser.add_argument("--source", default=None)
    return parser.parse_args()


def fail(message: str) -> None:
    print("FAIL: " + message)
    sys.exit(1)


def main() -> None:
    args = parse_args()
    address = args.contract
    print("Contract:", address)
    print("Explorer:", EXPLORER + address)

    client = create_client(chain=studionet)
    try:
        info = client.read_contract(
            address=address, function_name="get_protocol_info", args=[]
        )
    except Exception as exc:  # noqa: BLE001 - surface any RPC/contract error
        fail("get_protocol_info call failed: " + str(exc))

    print(json.dumps(info, indent=2, sort_keys=True))

    if info.get("schema") != EXPECTED_SCHEMA:
        fail("schema mismatch: expected " + EXPECTED_SCHEMA)
    bounds = info.get("bounds") or {}
    for key, expected in EXPECTED_BOUNDS.items():
        if bounds.get(key) != expected:
            fail("bound mismatch for " + key + ": expected " + str(expected))
    if set(info.get("verdicts") or []) != EXPECTED_VERDICTS:
        fail("verdict enum mismatch")
    if info.get("claim_states") != ["READY", "SETTLED", "VOID"]:
        fail("claim state enum mismatch")

    if args.claim:
        claim = client.read_contract(
            address=address, function_name="get_claim", args=[args.claim]
        )
        print("\nclaim " + args.claim + ":")
        print(json.dumps(claim, indent=2, sort_keys=True))
    if args.source:
        source = client.read_contract(
            address=address, function_name="get_source", args=[args.source]
        )
        print("\nsource " + args.source + ":")
        print(json.dumps(source, indent=2, sort_keys=True))

    print("\nOK: live contract matches schema", EXPECTED_SCHEMA)


if __name__ == "__main__":
    main()
