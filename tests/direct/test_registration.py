"""Source registration: validation, canonicalization, fingerprints, indexes."""

import hashlib
import json

from conftest import URLS, deploy, register


def test_register_returns_deterministic_fingerprint(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    fingerprint = register(contract, direct_vm, direct_alice)
    creator = "0x" + direct_alice.hex()
    expected = hashlib.sha256(
        json.dumps(
            [
                "PROOFMESH-SOURCE-DEFINITION-V1",
                {
                    "source_id": "a",
                    "creator": creator,
                    "url": URLS["a"],
                    "expected_hash": "",
                },
            ],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    assert fingerprint == expected
    record = contract.get_source("a")
    assert record["fingerprint"] == fingerprint
    assert record["status"] == "COMMITTED"
    assert record["url"] == URLS["a"]
    assert record["expected_hash"] == ""
    assert record["creator"] == creator
    assert contract.get_owner_source_ids(direct_alice) == ["a"]


def test_duplicate_id_and_duplicate_url_are_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice)
    with direct_vm.expect_revert("already registered"):
        register(contract, direct_vm, direct_alice)
    with direct_vm.expect_revert("already registered"):
        register(contract, direct_vm, direct_alice, "b", URLS["a"])
    assert contract.get_owner_source_ids(direct_alice) == ["a"]


def test_invalid_source_ids_are_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    for position, source_id in enumerate(
        ["", "bad id", "bad/slash", "bad:colon", "identifié", "x" * 97]
    ):
        with direct_vm.expect_revert():
            register(
                contract,
                direct_vm,
                direct_alice,
                source_id=source_id,
                url="https://reports.example.org/invalid-" + str(position),
            )
    assert contract.get_owner_source_ids(direct_alice) == []


def test_max_length_id_is_valid_and_bad_characters_are_rejected(
    direct_deploy, direct_vm, direct_alice
):
    contract = deploy(direct_deploy)
    maximum_id = "A" * 96
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id=maximum_id,
        url="https://reports.example.org/max",
    )
    assert contract.get_source(maximum_id)["source_id"] == maximum_id
    invalid = [
        " leading",
        "trailing ",
        "line\nbreak",
        "tab\tbreak",
        "control\x00break",
        "ｅvidence",  # full-width confusable
    ]
    for position, source_id in enumerate(invalid):
        with direct_vm.expect_revert():
            register(
                contract,
                direct_vm,
                direct_alice,
                source_id=source_id,
                url="https://reports.example.org/badid-" + str(position),
            )


def test_url_canonicalization_is_host_only(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id="a",
        url="HTTPS://BÜCHER.Example.COM:443/path/../item?x=1%2F2",
    )
    assert (
        contract.get_source("a")["url"]
        == "https://xn--bcher-kva.example.com/path/../item?x=1%2F2"
    )
    with direct_vm.expect_revert("already registered"):
        register(
            contract,
            direct_vm,
            direct_alice,
            source_id="b",
            url="https://xn--bcher-kva.example.com/path/../item?x=1%2F2",
        )
    # Different path spelling is a different source: paths are preserved.
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id="c",
        url="https://xn--bcher-kva.example.com/item?x=1%2F2",
    )
    with direct_vm.expect_revert():
        register(
            contract,
            direct_vm,
            direct_alice,
            source_id="d",
            url="https://reports.example.org./d",
        )


def test_invalid_urls_are_rejected(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    invalid_urls = [
        "",
        "http://reports.example.org/a",
        " https://reports.example.org/a",
        "https://reports.example.org/a ",
        "https://-bad.example/a",
        "https://example..com/a",
        "https://user:pass@reports.example.org/a",
        "https://reports.example.org/a#fragment",
        "https://reports.example.org:0/a",
        "https://reports.example.org:65536/a",
        "ftp://reports.example.org/a",
        "//reports.example.org/a",
        "https:///a",
        "x" * 2100,
    ]
    for position, url in enumerate(invalid_urls):
        with direct_vm.expect_revert():
            register(
                contract,
                direct_vm,
                direct_alice,
                source_id="u" + str(position),
                url=url,
            )
    assert contract.get_owner_source_ids(direct_alice) == []


def test_explicit_port_and_ip_hosts_are_canonical(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id="a",
        url="https://reports.example.org:8443/a",
    )
    assert contract.get_source("a")["url"] == "https://reports.example.org:8443/a"
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id="b",
        url="https://[2001:0DB8:0000:0000:0000:0000:0000:0001]/v6",
    )
    assert contract.get_source("b")["url"] == "https://[2001:db8::1]/v6"
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id="c",
        url="https://127.0.0.1/ip",
    )
    assert contract.get_source("c")["url"] == "https://127.0.0.1/ip"


def test_expected_hash_validation(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    digest = "ab" * 32
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id="a",
        url="https://reports.example.org/ha",
        expected_hash=digest.upper(),
    )
    assert contract.get_source("a")["expected_hash"] == digest
    register(
        contract,
        direct_vm,
        direct_alice,
        source_id="b",
        url="https://reports.example.org/hb",
        expected_hash="  ",
    )
    assert contract.get_source("b")["expected_hash"] == ""
    for bad in ["zz" * 32, "ab" * 31, "ab" * 33]:
        with direct_vm.expect_revert():
            register(
                contract,
                direct_vm,
                direct_alice,
                source_id="c-" + str(len(bad)),
                url="https://reports.example.org/bad-" + str(len(bad)),
                expected_hash=bad,
            )


def test_owner_indexes_are_sorted_and_per_owner(direct_deploy, direct_vm, direct_alice, direct_bob):
    contract = deploy(direct_deploy)
    register(contract, direct_vm, direct_alice, "zeta", "https://reports.example.org/z")
    register(contract, direct_vm, direct_bob, "beta", "https://reports.example.org/b")
    register(contract, direct_vm, direct_alice, "alpha", "https://reports.example.org/a")
    assert contract.get_owner_source_ids(direct_alice) == ["alpha", "zeta"]
    assert contract.get_owner_source_ids(direct_bob) == ["beta"]


def test_owner_index_is_bounded(direct_deploy, direct_vm, direct_alice):
    contract = deploy(direct_deploy)
    for index in range(128):
        register(
            contract,
            direct_vm,
            direct_alice,
            source_id="s" + str(index),
            url="https://reports.example.org/r" + str(index),
        )
    assert len(contract.get_owner_source_ids(direct_alice)) == 128
    with direct_vm.expect_revert("owner record index is full"):
        register(
            contract,
            direct_vm,
            direct_alice,
            source_id="overflow",
            url="https://reports.example.org/overflow",
        )


def test_unknown_source_raises(direct_deploy, direct_vm):
    contract = deploy(direct_deploy)
    with direct_vm.expect_revert("not registered"):
        contract.get_source("missing")
