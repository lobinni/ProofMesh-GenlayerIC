"""Shared helpers for ProofMesh direct-mode tests.

Direct mode runs the contract in memory with the web and LLM boundaries
mocked (~ms per test, no Studio required). Mocks only replace the
nondeterministic boundary; every deterministic layer (canonicalization,
validation, grouping, verdicts, fingerprints) executes for real.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "proof_mesh.py"

URLS = {
    "a": "https://reports.example.org/a",
    "b": "https://reports.example.org/b",
    "c": "https://reports.example.org/c",
    "d": "https://reports.example.org/d",
    "e": "https://reports.example.org/e",
    "f": "https://reports.example.org/f",
    "g": "https://reports.example.org/g",
    "h": "https://reports.example.org/h",
}

DEFAULT_STATEMENT = "The committed sources support the proposition."
DEFAULT_CRITERIA = "Count only independently originated supporting source groups."


def deploy(direct_deploy):
    return direct_deploy(CONTRACT)


def register(contract, direct_vm, sender, source_id="a", url=None, expected_hash=""):
    direct_vm.sender = sender
    target_url = url if url is not None else URLS.get(source_id, "https://reports.example.org/custom")
    return contract.register_source(source_id, target_url, expected_hash)


def open_claim(
    contract,
    direct_vm,
    sender,
    claim_id="claim-1",
    statement=DEFAULT_STATEMENT,
    criteria=DEFAULT_CRITERIA,
    source_ids=None,
    required_support_groups=1,
):
    direct_vm.sender = sender
    return contract.create_claim(
        claim_id,
        statement,
        criteria,
        source_ids if source_ids is not None else ["a"],
        required_support_groups,
    )


def semantic_result(positions, relations=None, reasoning="The bounded graph is internally consistent."):
    """Build a schema-valid semantic payload for the given positions.

    Relations are emitted for every pair of available (non-UNRESOLVED)
    sources, defaulting to INDEPENDENT unless overridden with a
    {(left, right): REL} mapping.
    """
    overrides = relations or {}
    ids = sorted(positions)
    edges = []
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            if positions[left] == "UNRESOLVED" or positions[right] == "UNRESOLVED":
                continue
            edges.append(
                {
                    "left_id": left,
                    "right_id": right,
                    "relation": overrides.get((left, right), "INDEPENDENT"),
                }
            )
    return {
        "positions": [
            {"source_id": source_id, "position": positions[source_id]}
            for source_id in ids
        ],
        "relations": edges,
        "reasoning": reasoning,
    }


def wire_observation(direct_vm, result, bodies=None, raw_payload=None):
    """Mock the web snapshots an LLM response for one assessment.

    `bodies` maps source_id -> text body, full response dict, or None to
    leave the URL unmocked (a fetch failure). `raw_payload` replaces the
    JSON-serialized semantic result entirely (for malformed-output tests).
    """
    direct_vm.clear_mocks()
    if bodies is None:
        ids = [item["source_id"] for item in result.get("positions", [])] or ["a"]
        bodies = {sid: "Snapshot text for " + sid for sid in ids if sid in URLS}
    for source_id, body in bodies.items():
        if body is None:
            continue
        response = body if isinstance(body, dict) else {"status": 200, "body": body}
        direct_vm.mock_web(re.escape(URLS[source_id]), response)
    payload = raw_payload if raw_payload is not None else json.dumps(result)
    direct_vm.mock_llm("SEMANTIC_TASK_V1", payload)


def setup_claim(contract, direct_vm, sender, source_ids, threshold=1):
    for source_id in source_ids:
        register(contract, direct_vm, sender, source_id)
    open_claim(
        contract,
        direct_vm,
        sender,
        source_ids=source_ids,
        required_support_groups=threshold,
    )


def settle(contract, direct_vm, sender, result, bodies=None, raw_payload=None, claim_id="claim-1"):
    wire_observation(direct_vm, result, bodies=bodies, raw_payload=raw_payload)
    direct_vm.sender = sender
    return contract.assess(claim_id)
