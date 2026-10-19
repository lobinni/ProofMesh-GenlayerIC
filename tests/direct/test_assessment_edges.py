"""Edge coverage: permissions, cross-owner references, budgets, ordering."""

import json
import re

from conftest import (
    URLS,
    deploy,
    open_claim,
    register,
    semantic_result,
    settle,
    setup_claim,
)


def test_assessment_is_permissionless(direct_deploy, direct_vm, direct_alice, direct_bob):
    """Anyone may assess a READY claim; ownership does not gate utility."""
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    result = settle(
        contract,
        direct_vm,
        direct_bob,  # not the claim creator
        semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}),
    )
    assert result["verdict"] == "ATTESTED"
    assert contract.get_owner_claim_ids(direct_alice) == ["claim-1"]
    assert contract.get_owner_claim_ids(direct_bob) == []


def test_claim_can_reference_sources_from_other_owners(
    direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie
):
    """The registry is public: claims may mix sources from any wallet."""
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice, "a")
    register(contract, direct_vm, direct_bob, "b")
    open_claim(contract, direct_vm, direct_charlie, "mixed", source_ids=["b", "a"])
    view = contract.get_claim("mixed")
    assert view["source_ids"] == ["a", "b"]
    assert view["creator"] == "0x" + direct_charlie.hex()
    assert contract.get_owner_claim_ids(direct_charlie) == ["mixed"]
    assert contract.get_owner_claim_ids(direct_alice) == []


def test_aggregate_budget_overflow_marks_later_sources_unavailable(
    direct_deploy, direct_vm, direct_alice
):
    """Sources beyond the 65,536-char aggregate budget lose availability."""
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b", "c"], threshold=1)
    result = settle(
        contract,
        direct_vm,
        direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "SUPPORTS", "c": "UNRESOLVED"}),
        bodies={
            "a": "a" * 32000,
            "b": "b" * 32000,  # 64,000 chars so far: under the 65,536 cap
            "c": "c" * 32000,  # would reach 96,000: c drops out
        },
    )
    assert result["verdict"] == "UNRESOLVED"  # rule 1: an unresolved position
    assert result["groups"] == [["a"], ["b"]]
    assert result["supporting_groups"] == 2
    view = contract.get_claim("claim-1")
    positions = {item["source_id"]: item["position"] for item in view["positions"]}
    assert positions["c"] == "UNRESOLVED"


def test_stored_relations_are_canonically_normalized(direct_deploy, direct_vm, direct_alice):
    """Reversed endpoints and scrambled edge order are normalized on store."""
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b", "c"], threshold=2)
    scrambled = {
        "positions": [
            {"source_id": "a", "position": "SUPPORTS"},
            {"source_id": "b", "position": "SUPPORTS"},
            {"source_id": "c", "position": "SUPPORTS"},
        ],
        "relations": [
            {"left_id": "c", "right_id": "a", "relation": "INDEPENDENT"},  # reversed
            {"left_id": "b", "right_id": "c", "relation": "INDEPENDENT"},
            {"left_id": "a", "right_id": "b", "relation": "SAME_ORIGIN"},
        ],
        "reasoning": "Scrambled order must normalize to the canonical graph.",
    }
    result = settle(contract, direct_vm, direct_alice, scrambled)
    assert result["verdict"] == "ATTESTED"
    view = contract.get_claim("claim-1")
    assert view["relations"] == [
        {"left_id": "a", "right_id": "b", "relation": "SAME_ORIGIN"},
        {"left_id": "a", "right_id": "c", "relation": "INDEPENDENT"},
        {"left_id": "b", "right_id": "c", "relation": "INDEPENDENT"},
    ]
    assert view["groups"] == [["a", "b"], ["c"]]


def test_per_source_limit_allows_exact_fit(direct_deploy, direct_vm, direct_alice):
    """A body of exactly MAX_FETCHED_CONTENT characters stays available."""
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    direct_vm.clear_mocks()
    direct_vm.mock_web(re.escape(URLS["a"]), {"status": 200, "body": "q" * 32768})
    direct_vm.mock_web(re.escape(URLS["b"]), {"status": 200, "body": "Snapshot text for b"})
    direct_vm.mock_llm(
        "SEMANTIC_TASK_V1",
        json.dumps(semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})),
    )
    direct_vm.sender = direct_alice
    result = contract.assess("claim-1")
    assert result["verdict"] == "ATTESTED"
