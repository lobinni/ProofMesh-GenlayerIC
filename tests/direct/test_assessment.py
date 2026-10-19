"""Assessment: verdicts, grouping rules, schema gates, fetch failure modes."""

import hashlib
import json

from conftest import (
    deploy,
    register,
    semantic_result,
    settle,
    setup_claim,
)


def test_two_independent_supporters_attest(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}),
    )
    assert result["verdict"] == "ATTESTED"
    assert result["state"] == "SETTLED"
    assert result["groups"] == [["a"], ["b"]]
    assert result["graph_consistent"] is True
    assert result["supporting_groups"] == 2
    assert result["refuting_groups"] == 0
    view = contract.get_claim("claim-1")
    assert view["state"] == "SETTLED"
    assert view["verdict"] == "ATTESTED"
    assert view["groups"] == [["a"], ["b"]]
    assert view["reasoning"] == "The bounded graph is internally consistent."


def test_single_source_can_attest_with_threshold_one(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a"], threshold=1)
    result = settle(
        contract, direct_vm, direct_alice, semantic_result({"a": "SUPPORTS"})
    )
    assert result["verdict"] == "ATTESTED"
    assert result["groups"] == [["a"]]


def test_support_and_refutation_dispute(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "REFUTES"}),
    )
    assert result["verdict"] == "DISPUTED"
    assert result["supporting_groups"] == 1
    assert result["refuting_groups"] == 1


def test_refutation_without_support_is_insufficient(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result({"a": "REFUTES", "b": "REFUTES"}),
    )
    assert result["verdict"] == "INSUFFICIENT"
    assert result["supporting_groups"] == 0
    assert result["refuting_groups"] == 2


def test_neutral_only_is_insufficient(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result({"a": "NEUTRAL", "b": "NEUTRAL"}),
    )
    assert result["verdict"] == "INSUFFICIENT"


def test_support_below_threshold_is_insufficient(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "NEUTRAL"}),
    )
    assert result["verdict"] == "INSUFFICIENT"


def test_same_origin_copies_count_as_one_group(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b", "c", "d"], threshold=3)
    related = {("a", "b"): "SAME_ORIGIN", ("c", "d"): "DERIVED"}
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result(
            {"a": "SUPPORTS", "b": "SUPPORTS", "c": "SUPPORTS", "d": "SUPPORTS"},
            related,
        ),
    )
    assert result["groups"] == [["a", "b"], ["c", "d"]]
    assert result["supporting_groups"] == 2
    assert result["verdict"] == "INSUFFICIENT"  # four URLs, two independent voices


def test_derived_chain_collapses_to_one_voice(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b", "c", "d"], threshold=2)
    related = {("a", "b"): "DERIVED", ("b", "c"): "SAME_ORIGIN"}
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result(
            {"a": "SUPPORTS", "b": "SUPPORTS", "c": "SUPPORTS", "d": "SUPPORTS"},
            related,
        ),
    )
    assert result["groups"] == [["a", "b", "c"], ["d"]]
    assert result["supporting_groups"] == 2
    assert result["verdict"] == "ATTESTED"


def test_unclear_relation_is_conservative(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result(
            {"a": "SUPPORTS", "b": "SUPPORTS"}, {("a", "b"): "UNCLEAR"}
        ),
    )
    assert result["groups"] == [["a", "b"]]
    assert result["verdict"] == "INSUFFICIENT"


def test_inconsistent_graph_is_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b", "c"], threshold=1)
    related = {
        ("a", "b"): "SAME_ORIGIN",
        ("b", "c"): "SAME_ORIGIN",
        ("a", "c"): "INDEPENDENT",  # contradiction: a and c already joined
    }
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "SUPPORTS", "c": "SUPPORTS"}, related),
    )
    assert result["verdict"] == "UNRESOLVED"
    assert result["graph_consistent"] is False
    assert result["groups"] == [["a", "b", "c"]]


def test_mixed_stance_inside_one_group_is_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result = settle(
        contract, direct_vm, direct_alice,
        semantic_result(
            {"a": "SUPPORTS", "b": "REFUTES"}, {("a", "b"): "SAME_ORIGIN"}
        ),
    )
    assert result["verdict"] == "UNRESOLVED"


def test_unresolved_position_forces_unresolved_verdict(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result = settle(
        contract,
        direct_vm,
        direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "UNRESOLVED"}),
        bodies={"a": "Snapshot text for a", "b": None},
    )
    assert result["verdict"] == "UNRESOLVED"
    view = contract.get_claim("claim-1")
    positions_by_id = {item["source_id"]: item["position"] for item in view["positions"]}
    assert positions_by_id == {"a": "SUPPORTS", "b": "UNRESOLVED"}
    assert view["relations"] == []


def test_assessment_is_one_shot(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a"], threshold=1)
    settle(contract, direct_vm, direct_alice, semantic_result({"a": "SUPPORTS"}))
    assert contract.get_claim("claim-1")["state"] == "SETTLED"
    with direct_vm.expect_revert("not ready"):
        settle(contract, direct_vm, direct_alice, semantic_result({"a": "SUPPORTS"}))
    with direct_vm.expect_revert("only a READY claim"):
        direct_vm.sender = direct_alice
        contract.void_claim("claim-1")


def test_missing_pair_edge_is_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    broken = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    broken["relations"] = []
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, broken)
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_duplicate_pair_edge_is_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    broken = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    broken["relations"].append(dict(broken["relations"][0]))
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, broken)
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_reverse_duplicate_edge_is_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    broken = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    broken["relations"].append(
        {"left_id": "b", "right_id": "a", "relation": "INDEPENDENT"}
    )
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, broken)
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_self_edge_is_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    broken = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    broken["relations"][0] = {"left_id": "a", "right_id": "a", "relation": "INDEPENDENT"}
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, broken)
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_invalid_enums_are_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    bad_position = semantic_result({"a": "BACKS", "b": "SUPPORTS"})
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, bad_position)
    bad_relation = semantic_result(
        {"a": "SUPPORTS", "b": "SUPPORTS"}, {("a", "b"): "COPYED"}
    )
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, bad_relation)
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_missing_and_unknown_positions_are_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    missing = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    missing["positions"] = missing["positions"][:1]
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, missing)
    unknown = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    unknown["positions"][1] = {"source_id": "zz", "position": "SUPPORTS"}
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, unknown)
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_extra_keys_and_reasoning_bounds_are_enforced(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    extra = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    extra["notes"] = "unexpected"
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, extra)
    empty_reasoning = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}, reasoning="  ")
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, empty_reasoning)
    long_reasoning = semantic_result(
        {"a": "SUPPORTS", "b": "SUPPORTS"}, reasoning="r" * 2001
    )
    with direct_vm.expect_revert():
        settle(contract, direct_vm, direct_alice, long_reasoning)
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_malformed_json_payload_is_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a"], threshold=1)
    with direct_vm.expect_revert():
        settle(
            contract, direct_vm, direct_alice, {}, raw_payload="not json at all"
        )
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_fetch_failure_marks_source_unresolved(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result = settle(
        contract,
        direct_vm,
        direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "UNRESOLVED"}),
        bodies={"a": "Snapshot text for a", "b": {"status": 500, "body": "boom"}},
    )
    assert result["verdict"] == "UNRESOLVED"


def test_oversized_and_empty_snapshots_are_unavailable(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result = settle(
        contract,
        direct_vm,
        direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "UNRESOLVED"}),
        bodies={"a": "Snapshot text for a", "b": "x" * 40000},
    )
    assert result["verdict"] == "UNRESOLVED"

    contract2 = deploy(direct_deploy)
    setup_claim(contract2, direct_vm, direct_alice, ["a", "b"], threshold=1)
    result2 = settle(
        contract2,
        direct_vm,
        direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "UNRESOLVED"}),
        bodies={"a": "Snapshot text for a", "b": "   "},
    )
    assert result2["verdict"] == "UNRESOLVED"


def test_model_cannot_upgrade_an_unavailable_source(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    lying = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    with direct_vm.expect_revert("UNRESOLVED"):
        settle(
            contract, direct_vm, direct_alice, lying,
            bodies={"a": "Snapshot text for a", "b": None},
        )
    assert contract.get_claim("claim-1")["state"] == "READY"


def test_expected_hash_gate(direct_deploy, direct_vm, direct_alice):
    from conftest import open_claim

    contract = deploy(direct_deploy)
    body = "Authentic snapshot text for a."
    good_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    register(contract, direct_vm, direct_alice, "a", expected_hash=good_hash)
    register(contract, direct_vm, direct_alice, "b")
    open_claim(contract, direct_vm, direct_alice, "claim-1", source_ids=["a", "b"])
    result = settle(
        contract,
        direct_vm,
        direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}),
        bodies={"a": body, "b": "Snapshot text for b"},
    )
    assert result["verdict"] == "ATTESTED"

    # A mutated body fails the committed hash and becomes UNRESOLVED.
    contract2 = deploy(direct_deploy)
    register(contract2, direct_vm, direct_alice, "a", expected_hash=good_hash)
    register(contract2, direct_vm, direct_alice, "b")
    open_claim(contract2, direct_vm, direct_alice, "claim-1", source_ids=["a", "b"])
    result2 = settle(
        contract2,
        direct_vm,
        direct_alice,
        semantic_result({"a": "UNRESOLVED", "b": "SUPPORTS"}),
        bodies={"a": "tampered body", "b": "Snapshot text for b"},
    )
    assert result2["verdict"] == "UNRESOLVED"


def test_result_fingerprint_is_deterministic_and_complete(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    semantic = semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"})
    result = settle(contract, direct_vm, direct_alice, semantic)
    expected_groups = {
        "groups": [["a"], ["b"]],
        "consistent": True,
        "supporting_groups": 2,
        "refuting_groups": 0,
    }
    expected = hashlib.sha256(
        json.dumps(
            [
                "PROOFMESH-RESULT-V1",
                {
                    "claim_id": "claim-1",
                    "verdict": "ATTESTED",
                    "positions": semantic["positions"],
                    "relations": semantic["relations"],
                    "groups": expected_groups,
                    "reasoning": semantic["reasoning"],
                },
            ],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert result["result_fingerprint"] == expected
    assert contract.get_claim("claim-1")["result_fingerprint"] == expected


def test_claim_constructor_unknown_id_raises(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    with direct_vm.expect_revert("not registered"):
        direct_vm.sender = direct_alice
        contract.assess("ghost")
