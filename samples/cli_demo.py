#!/usr/bin/env python3
"""End-to-end ProofMesh demo over the genlayer-py SDK.

Runs the full lifecycle against a deployed ProofMesh contract:
register two sources, open one claim, assess it, print the settled
record. Requires the contract to be deployed already (see
docs/DEPLOYMENT.md).

Usage:

    pip install genlayer-py
    python samples/cli_demo.py                     # runs against the live Studionet deployment
    python samples/cli_demo.py --contract 0xYour   # or your own deployment

Options:

    --contract 0x...           target contract (default: the verified
                               Studionet deployment)
    --private-key 0x...        use an existing account key, otherwise a
                               fresh throwaway account is generated
    --prefix demo              id prefix so reruns never collide

The script performs real validator work: assess takes minutes to
finalize on a healthy network.
"""

from __future__ import annotations

import argparse
import json
import time
import uuid

from genlayer_py import create_account, create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus


STATEMENT = "Example domains are reserved for use in documentation."
CRITERIA = (
    "Support requires the page itself to state or demonstrate the "
    "documentation purpose of the domain. Mere mention is NEUTRAL."
)

DEFAULT_CONTRACT = "0xC99B99b6A22D01629Bd21fA543E3e7E583E5EF3F"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract",
        default=DEFAULT_CONTRACT,
        help="deployed contract address (default: the verified Studionet deployment)",
    )
    parser.add_argument("--private-key", default=None, help="hex private key (optional)")
    parser.add_argument("--prefix", default=None, help="id prefix (default: random)")
    return parser.parse_args()


def build_client(private_key: str | None):
    if private_key:
        account = create_account(private_key)
    else:
        account = create_account()
        print("Generated throwaway account. Fund it before running writes:")
        print("  address:", account.address)
        input("Press ENTER once funded... ")
    return create_client(chain=studionet, account=account), account


def write_and_wait(client, account, address, function_name, args):
    tx_hash = client.write_contract(
        account=account,
        address=address,
        function_name=function_name,
        args=args,
        value=0,
    )
    print(f"  submitted {function_name}: {tx_hash}")
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hash,
        status=TransactionStatus.FINALIZED,
    )
    result = receipt.get("tx_execution_result_name", "UNKNOWN")
    print(f"  finalized with {result}")
    return receipt


def main() -> None:
    args = parse_args()
    client, account = build_client(args.private_key)
    prefix = args.prefix or ("demo-" + uuid.uuid4().hex[:8])
    source_one = prefix + "-iana"
    source_two = prefix + "-iana-managed"
    claim_id = prefix + "-claim"

    print("\n[1/4] register sources")
    write_and_wait(
        client, account, args.contract, "register_source",
        [source_one, "https://www.iana.org/domains/example", ""],
    )
    write_and_wait(
        client, account, args.contract, "register_source",
        [source_two, "https://www.iana.org/domains", ""],
    )

    print("\n[2/4] create claim")
    write_and_wait(
        client, account, args.contract, "create_claim",
        [claim_id, STATEMENT, CRITERIA, [source_one, source_two], 1],
    )

    print("\n[3/4] assess (real consensus, minutes)")
    started = time.time()
    write_and_wait(client, account, args.contract, "assess", [claim_id])
    print(f"  consensus finished in {time.time() - started:.0f}s")

    print("\n[4/4] read back the settled claim")
    settled = client.read_contract(
        address=args.contract,
        function_name="get_claim",
        args=[claim_id],
    )
    print(json.dumps(settled, indent=2, sort_keys=True))
    verdict = settled.get("verdict")
    print(f"\nVerdict for {claim_id}: {verdict}")
    print("Groups:", settled.get("groups"))


if __name__ == "__main__":
    main()
