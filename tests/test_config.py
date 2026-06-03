"""Tests for ocpp_rag.config module."""

from pathlib import Path

from ocpp_rag.config import (
    CACHE_DIR,
    CHROMA_DIR,
    COLLECTION_NAME,
    FUNCTIONAL_BLOCKS,
)


class TestPaths:
    def test_cache_dir_is_path(self):
        assert isinstance(CACHE_DIR, Path)

    def test_chroma_dir_under_cache(self):
        assert CHROMA_DIR == CACHE_DIR / "chroma_db"


class TestCollectionName:
    def test_collection_name_value(self):
        assert COLLECTION_NAME == "ocpp_knowledge"


class TestFunctionalBlocks:
    def test_covers_a_through_p(self):
        for letter in [chr(i) for i in range(ord("A"), ord("P") + 1)]:
            assert letter in FUNCTIONAL_BLOCKS

    def test_exactly_16_blocks(self):
        assert len(FUNCTIONAL_BLOCKS) == 16

    def test_specific_block_names(self):
        assert FUNCTIONAL_BLOCKS["A"] == "Security"
        assert FUNCTIONAL_BLOCKS["E"] == "Transactions"
        assert FUNCTIONAL_BLOCKS["K"] == "SmartCharging"
        assert FUNCTIONAL_BLOCKS["P"] == "DataTransfer"

    def test_no_duplicate_values(self):
        values = list(FUNCTIONAL_BLOCKS.values())
        assert len(values) == len(set(values))
