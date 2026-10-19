"""Claim creation, thresholds, views, void lifecycle, protocol metadata."""

import hashlib
import json

from conftest import (
    DEFAULT_CRITERIA,
    DEFAULT_STATEMENT,
    deploy,
    open_claim,
    register,
    setup_claim,
)


def test_create_claim_returns_deterministic_fingerprint(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice)
    register(contract, direct_vm, direct_alice, "b")
    fingerprint = open_claim(
        contract, direct_vm, direct_alice, source_ids=["b", "a"], required_support_groups=1
    )
    creator = "0x" + direct_alice.hex()
    expected = hashlib.sha256(
        json.dumps(
            [
                "PROOFMESH-CLAIM-DEFINITION-V1",
                {
                    "claim_id": "claim-1",
                    "creator": creator,
                    "statement": DEFAULT_STATEMENT,
                    "criteria": DEFAULT_CRITERIA,
                    "source_ids": ["a", "b"],
                    "required_support_groups": 1,
                },
            ],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert fingerprint == expected
    view = contract.get_claim("claim-1")
    assert view["fingerprint"] == fingerprint
    assert view["state"] == "READY"
    assert view["source_ids"] == ["a", "b"]
    assert view["required_support_groups"] == 1
    assert view["verdict"] == ""
    assert view["positions"] is None
    assert view["relations"] is None
    assert view["groups"] is None
    assert view["graph_consistent"] is None
    assert view["reasoning"] is None
    assert view["result_fingerprint"] is None
    assert contract.get_claim_fingerprint("claim-1") == fingerprint
    assert contract.get_owner_claim_ids(direct_alice) == ["claim-1"]


def test_source_ids_are_deduplicated_and_sorted(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    for source_id in ["a", "b", "c"]:
        register(contract, direct_vm, direct_alice, source_id)
    open_claim(contract, direct_vm, direct_alice, source_ids=["c", "a", "c", "b"])
    assert contract.get_claim("claim-1")["source_ids"] == ["a", "b", "c"]


def test_threshold_bounds_are_enforced(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    for source_id in ["a", "b", "c"]:
        register(contract, direct_vm, direct_alice, source_id)
    with direct_vm.expect_revert():
        open_claim(contract, direct_vm, direct_alice, "t0", source_ids=["a"], required_support_groups=0)
    with direct_vm.expect_revert():
        open_claim(
            contract, direct_vm, direct_alice, "t4",
            source_ids=["a", "b", "c"], required_support_groups=4,
        )
    open_claim(
        contract, direct_vm, direct_alice, "t3",
        source_ids=["a", "b", "c"], required_support_groups=3,
    )
    assert contract.get_claim("t3")["required_support_groups"] == 3


def test_unknown_or_excessive_sources_are_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice)
    with direct_vm.expect_revert("not registered"):
        open_claim(contract, direct_vm, direct_alice, "missing", source_ids=["a", "zz"])
    for source_id in ["b", "c", "d", "e", "f", "g", "h"]:
        register(contract, direct_vm, direct_alice, source_id)
    with direct_vm.expect_revert():
        open_claim(contract, direct_vm, direct_alice, "empty", source_ids=[])


def test_nine_distinct_sources_are_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    ids = ["s" + str(index) for index in range(9)]
    for source_id in ids:
        register(
            contract, direct_vm, direct_alice,
            source_id, "https://reports.example.org/" + source_id,
        )
    with direct_vm.expect_revert("between 1 and 8"):
        open_claim(contract, direct_vm, direct_alice, "nine", source_ids=ids)


def test_statement_and_criteria_bounds(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice)
    open_claim(contract, direct_vm, direct_alice, "ok", statement="s" * 8000, criteria="c" * 4000)
    with direct_vm.expect_revert():
        open_claim(contract, direct_vm, direct_alice, "bad-s", statement="s" * 8001)
    with direct_vm.expect_revert():
        open_claim(contract, direct_vm, direct_alice, "bad-c", criteria="c" * 4001)
    with direct_vm.expect_revert():
        open_claim(contract, direct_vm, direct_alice, "blank-s", statement="   ")
    with direct_vm.expect_revert():
        open_claim(contract, direct_vm, direct_alice, "blank-c", criteria="")


def test_claim_id_rules_and_duplicates(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice)
    open_claim(contract, direct_vm, direct_alice, "C" * 96)
    with direct_vm.expect_revert("already registered"):
        open_claim(contract, direct_vm, direct_alice, "C" * 96)
    with direct_vm.expect_revert():
        open_claim(contract, direct_vm, direct_alice, "bad id")


def test_owner_claim_index_is_sorted_and_per_owner(direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice)
    register(contract, direct_vm, direct_bob, "b")
    open_claim(contract, direct_vm, direct_alice, "z-claim", source_ids=["a"])
    open_claim(contract, direct_vm, direct_bob, "m-claim", source_ids=["b"])
    open_claim(contract, direct_vm, direct_alice, "a-claim", source_ids=["a"])
    assert contract.get_owner_claim_ids(direct_alice) == ["a-claim", "z-claim"]
    assert contract.get_owner_claim_ids(direct_bob) == ["m-claim"]


def test_void_claim_lifecycle(direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a"])
    with direct_vm.expect_revert("only the claim creator"):
        direct_vm.sender = direct_bob
        contract.void_claim("claim-1")
    direct_vm.sender = direct_alice
    assert contract.void_claim("claim-1") == "VOID"
    assert contract.get_claim("claim-1")["state"] == "VOID"
    with direct_vm.expect_revert("only a READY claim"):
        direct_vm.sender = direct_alice
        contract.void_claim("claim-1")
    with direct_vm.expect_revert("not ready"):
        direct_vm.sender = direct_alice
        contract.assess("claim-1")


def test_void_unknown_claim_raises(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    with direct_vm.expect_revert("not registered"):
        direct_vm.sender = direct_alice
        contract.void_claim("ghost")


def test_get_protocol_info_shape(direct_deploy, direct_vm):
    contract = deploy(direct_deploy)
    info = contract.get_protocol_info()
    assert info["schema"] == "proofmesh.v1"
    assert info["bounds"]["max_sources_per_claim"] == 8
    assert info["bounds"]["max_pairs_per_claim"] == 28
    assert info["bounds"]["max_fetched_content_per_source"] == 32768
    assert info["bounds"]["max_total_fetched_content"] == 65536
    assert info["bounds"]["max_owner_records"] == 128
    assert info["claim_states"] == ["READY", "SETTLED", "VOID"]
    assert info["verdicts"] == ["ATTESTED", "DISPUTED", "INSUFFICIENT", "UNRESOLVED"]
    assert info["positions"] == ["NEUTRAL", "REFUTES", "SUPPORTS", "UNRESOLVED"]
    assert info["relations"] == ["DERIVED", "INDEPENDENT", "SAME_ORIGIN", "UNCLEAR"]


def test_assess_ready_guard_blocks_reentry(direct_deploy, direct_vm, direct_alice):
    # Without mocks wired, assessment must fail at the nondet boundary and
    # the claim must stay READY (nothing partially written).
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a"])
    direct_vm.clear_mocks()
    direct_vm.sender = direct_alice
    try:
        contract.assess("claim-1")
        raised = False
    except Exception:
        raised = True
    assert raised
    assert contract.get_claim("claim-1")["state"] == "READY"
