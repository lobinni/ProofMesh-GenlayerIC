"""Validator-side consensus behavior in direct mode.

Direct mode executes the leader function when the write method runs and
captures the validator closure. `direct_vm.run_validator()` re-executes the
validator against the current mocks, so mocks can be swapped between the
two phases to simulate a leader whose proposal must be rejected. These
tests exercise the parts of the validator that enforce: (1) independent
re-derivation of the semantic projection, and (2) availability agreement
between leader and validator snapshots.
"""

import json
import re

from conftest import URLS, deploy, semantic_result, setup_claim, settle


def test_validator_accepts_an_honest_leader(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    settle(contract, direct_vm, direct_alice, semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}))
    assert direct_vm.run_validator() is True


def test_validator_rejects_a_divergent_semantic_view(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=2)
    settle(contract, direct_vm, direct_alice, semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}))
    # Swap only the model's answer: the validator now derives a different
    # projection from the same snapshots and must reject the leader's.
    direct_vm.clear_mocks()
    direct_vm.mock_web(re.escape(URLS["a"]), {"status": 200, "body": "Snapshot text for a"})
    direct_vm.mock_web(re.escape(URLS["b"]), {"status": 200, "body": "Snapshot text for b"})
    direct_vm.mock_llm(
        "SEMANTIC_TASK_V1",
        json.dumps(semantic_result({"a": "SUPPORTS", "b": "REFUTES"})),
    )
    assert direct_vm.run_validator() is False


def test_validator_rejects_when_snapshot_availability_diverges(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    settle(
        contract,
        direct_vm,
        direct_alice,
        semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}),
        bodies={"a": "Snapshot text for a", "b": "Snapshot text for b"},
    )
    # Simulate a validator node where source b fails to fetch: the
    # validator's availability set must diverge from the leader's and the
    # proposal must be rejected even when the model output still matches.
    direct_vm.clear_mocks()
    direct_vm.mock_web(re.escape(URLS["a"]), {"status": 200, "body": "Snapshot text for a"})
    direct_vm.mock_llm(
        "SEMANTIC_TASK_V1",
        json.dumps(semantic_result({"a": "SUPPORTS", "b": "UNRESOLVED"})),
    )
    assert direct_vm.run_validator() is False


def test_validator_rejects_an_invalid_own_derivation(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    setup_claim(contract, direct_vm, direct_alice, ["a", "b"], threshold=1)
    settle(contract, direct_vm, direct_alice, semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}))
    # If the validator's own re-derivation fails schema validation (here an
    # over-long reasoning block), it cannot confirm anything and must
    # reject rather than accept a payload it could not verify.
    direct_vm.clear_mocks()
    direct_vm.mock_web(re.escape(URLS["a"]), {"status": 200, "body": "Snapshot text for a"})
    direct_vm.mock_web(re.escape(URLS["b"]), {"status": 200, "body": "Snapshot text for b"})
    direct_vm.mock_llm(
        "SEMANTIC_TASK_V1",
        json.dumps(semantic_result({"a": "SUPPORTS", "b": "SUPPORTS"}, reasoning="r" * 2001)),
    )
    assert direct_vm.run_validator() is False
