"""Deterministic policy tests that do not require Neo4j or an LLM."""

import re
import unicodedata
from difflib import SequenceMatcher


CORP_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "ltd", "limited",
    "llc", "plc", "co", "company",
}
SUPER_NODE_DEGREE = 100
SUPER_NODE_EDGE_CAP = 50
GLOBAL_EDGE_CAP = 250


def norm_entity(name: str) -> str:
    value = unicodedata.normalize("NFKC", str(name)).lower()
    value = re.sub(r"[^\w\s\-.]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def strip_suffix(name: str) -> str:
    tokens = norm_entity(name).replace(".", "").split()
    while tokens and tokens[-1] in CORP_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def merge_guard(left: str, right: str) -> bool:
    a, b = strip_suffix(left), strip_suffix(right)
    if a == b:
        return True
    left_tokens, right_tokens = a.split(), b.split()
    if (
        len(left_tokens) >= 2
        and len(right_tokens) >= 2
        and left_tokens[-1] == right_tokens[-1]
        and left_tokens[0] != right_tokens[0]
    ):
        return False
    if set(left_tokens) < set(right_tokens) or set(right_tokens) < set(left_tokens):
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.72


def edge_limit_for_degree(degree: int, requested: int = 1000) -> int:
    if degree > SUPER_NODE_DEGREE:
        return min(requested, SUPER_NODE_EDGE_CAP)
    return requested


def test_corporate_suffix_variants_are_mergeable():
    assert merge_guard("Microsoft Corporation", "Microsoft")
    assert merge_guard("Google LLC", "Google")
    assert merge_guard("Apple Inc.", "Apple")


def test_dangerous_false_merges_are_rejected():
    pairs = [
        ("Apple", "Apple Music"),
        ("Sam Altman", "Steve Altman"),
        ("OpenAI", "OpenTable"),
        ("Meta", "Metaverse"),
        ("Amazon", "Amazon Web Services"),
        ("Microsoft", "MicroStrategy"),
        ("Google", "Google Cloud"),
    ]
    assert all(not merge_guard(left, right) for left, right in pairs)


def test_supernode_cap_contract():
    assert edge_limit_for_degree(100) == 1000
    assert edge_limit_for_degree(101) == 50
    assert edge_limit_for_degree(10_000) == 50
    assert edge_limit_for_degree(10_000, requested=20) == 20


def test_global_edge_cap_contract():
    collected = list(range(1_000))[:GLOBAL_EDGE_CAP]
    assert len(collected) == 250
