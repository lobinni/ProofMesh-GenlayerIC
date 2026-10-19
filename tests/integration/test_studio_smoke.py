"""Integration smoke tests for ProofMesh against a live GenLayer network.

These tests deploy the contract and exercise the full leader/validator
consensus path with real web fetches and real model calls. They are slow
(minutes) and require a running environment (Studio, studionet, or a
devnet), so they are skipped by default.

Run them explicitly with:

    PROOFMESH_INTEGRATION=1 gltest tests/integration/ -v -s

Configure the target network in gltest.config.yaml first. The flow mirrors
samples/studio_walkthrough.md, which contains the same sequence as a
manual Studio checklist.
"""

import os
import uuid

import pytest


pytestmark = pytest.mark.skipif(
    os.environ.get("PROOFMESH_INTEGRATION") != "1",
    reason="integration tests are opt-in: set PROOFMESH_INTEGRATION=1",
)

# Stable, lightweight, long-lived pages for real web fetches.
SOURCE_ONE = "https://example.com/"
SOURCE_TWO = "https://www.iana.org/domains/example"


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


def test_register_and_read_back(default_account):
    from gltest import get_contract_factory
    from gltest.assertions import tx_execution_succeeded

    factory = get_contract_factory("ProofMesh")
    contract = factory.deploy(account=default_account)

    source_id = "int-" + _suffix()
    receipt = contract.register_source(args=[source_id, SOURCE_ONE, ""]).transact()
    assert tx_execution_succeeded(receipt)

    record = contract.get_source(args=[source_id]).call()
    assert record["source_id"] == source_id
    assert record["url"] == SOURCE_ONE
    assert record["status"] == "COMMITTED"

    ids = contract.get_owner_source_ids(args=[default_account.address]).call()
    assert source_id in ids


def test_protocol_info_is_available(default_account):
    from gltest import get_contract_factory

    factory = get_contract_factory("ProofMesh")
    contract = factory.deploy(account=default_account)
    info = contract.get_protocol_info().call()
    assert info["schema"] == "proofmesh.v1"
    assert info["bounds"]["max_sources_per_claim"] == 8
    assert set(info["verdicts"]) == {
        "ATTESTED",
        "DISPUTED",
        "INSUFFICIENT",
        "UNRESOLVED",
    }


def test_full_assessment_flow(default_account):
    """End-to-end: two public sources under real multi-validator consensus.

    The only hard assertions are finalization invariants: a valid verdict,
    bounded groups, and a 64-hex result fingerprint. The concrete verdict
    depends on live model reads of live pages, which is the point of
    running this against a real network.
    """
    from gltest import get_contract_factory
    from gltest.assertions import tx_execution_succeeded

    factory = get_contract_factory("ProofMesh")
    contract = factory.deploy(account=default_account)

    source_a = "int-a-" + _suffix()
    source_b = "int-b-" + _suffix()
    assert tx_execution_succeeded(
        contract.register_source(args=[source_a, SOURCE_ONE, ""]).transact()
    )
    assert tx_execution_succeeded(
        contract.register_source(args=[source_b, SOURCE_TWO, ""]).transact()
    )

    claim_id = "int-c-" + _suffix()
    assert tx_execution_succeeded(
        contract.create_claim(
            args=[
                claim_id,
                "Example domains are reserved for documentation.",
                "Support requires the page itself to state or demonstrate "
                "the documentation purpose of the domain.",
                [source_a, source_b],
                1,
            ]
        ).transact()
    )

    assert tx_execution_succeeded(contract.assess(args=[claim_id]).transact())
    settled = contract.get_claim(args=[claim_id]).call()
    assert settled["state"] == "SETTLED"
    assert settled["verdict"] in {
        "ATTESTED",
        "DISPUTED",
        "INSUFFICIENT",
        "UNRESOLVED",
    }
    assert isinstance(settled["result_fingerprint"], str)
    assert len(settled["result_fingerprint"]) == 64
