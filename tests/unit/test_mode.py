import pytest

from quantum_ads.core.safety.mode import MutationBlocked, SafetyMode


def test_read_only_blocks_mutation():
    with pytest.raises(MutationBlocked):
        SafetyMode(read_only=True).guard_mutation("ads.campaign.create")


def test_read_only_allows_reads_noop():
    SafetyMode(read_only=True).guard_read("ads.gaql.query")  # no raise


def test_mutation_allowed_when_read_only_off():
    SafetyMode(read_only=False).guard_mutation("ads.campaign.create")  # no raise
