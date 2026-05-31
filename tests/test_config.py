"""Tests for ocpp_rag.config module."""

from pathlib import Path

from ocpp_rag.config import (
    ROOT_DIR,
    SOURCE_DOCS_DIR,
    OUTPUT_DIR,
    PARSED_DIR,
    CHUNKS_DIR,
    CHROMA_DIR,
    SCHEMAS_DIR,
    APPENDICES_DIR,
    COLLECTION_NAME,
    OCPP_201_DOCS,
    OCPP_16_DOCS,
    OTHER_DOCS,
    ALL_DOCS,
    FUNCTIONAL_BLOCKS,
)


class TestPaths:
    """Test that all config paths are defined and consistent."""

    def test_root_dir_is_path(self):
        assert isinstance(ROOT_DIR, Path)

    def test_source_docs_dir_under_root(self):
        assert SOURCE_DOCS_DIR == ROOT_DIR / "source_docs"

    def test_output_dir_under_root(self):
        assert OUTPUT_DIR == ROOT_DIR / "output"

    def test_parsed_dir_under_output(self):
        assert PARSED_DIR == OUTPUT_DIR / "parsed"

    def test_chunks_dir_under_output(self):
        assert CHUNKS_DIR == OUTPUT_DIR / "chunks"

    def test_chroma_dir_under_cache(self):
        from ocpp_rag.config import CACHE_DIR
        assert CHROMA_DIR == CACHE_DIR / "chroma_db"

    def test_schemas_dir_under_output(self):
        assert SCHEMAS_DIR == OUTPUT_DIR / "schemas"

    def test_appendices_dir_under_output(self):
        assert APPENDICES_DIR == OUTPUT_DIR / "appendices"


class TestCollectionName:
    def test_collection_name_is_string(self):
        assert isinstance(COLLECTION_NAME, str)
        assert len(COLLECTION_NAME) > 0

    def test_collection_name_value(self):
        assert COLLECTION_NAME == "ocpp_knowledge"


class TestAllDocs:
    """Test that ALL_DOCS has expected entries."""

    def test_all_docs_is_union_of_sub_dicts(self):
        assert ALL_DOCS == {**OCPP_201_DOCS, **OCPP_16_DOCS, **OTHER_DOCS}

    def test_all_docs_has_ocpp201_part2(self):
        assert "ocpp201_part2" in ALL_DOCS

    def test_all_docs_has_ocpp16_spec(self):
        assert "ocpp16_spec" in ALL_DOCS

    def test_all_docs_has_ocpp16_j(self):
        assert "ocpp16_j" in ALL_DOCS

    def test_ocpp201_docs_count(self):
        assert len(OCPP_201_DOCS) == 8

    def test_ocpp16_docs_count(self):
        assert len(OCPP_16_DOCS) == 2

    def test_each_doc_has_required_fields(self):
        for doc_id, doc_info in ALL_DOCS.items():
            assert "title" in doc_info, f"{doc_id} missing 'title'"
            assert "file" in doc_info, f"{doc_id} missing 'file'"
            assert "ocpp_version" in doc_info, f"{doc_id} missing 'ocpp_version'"

    def test_ocpp201_docs_have_version_201(self):
        for doc_id, doc_info in OCPP_201_DOCS.items():
            assert doc_info["ocpp_version"] == "2.0.1", f"{doc_id} should be version 2.0.1"

    def test_ocpp16_docs_have_version_16(self):
        for doc_id, doc_info in OCPP_16_DOCS.items():
            assert doc_info["ocpp_version"] == "1.6", f"{doc_id} should be version 1.6"

    def test_file_paths_are_relative(self):
        for doc_id, doc_info in ALL_DOCS.items():
            path = doc_info["file"]
            assert not path.startswith("/"), f"{doc_id} file path should be relative"


class TestFunctionalBlocks:
    """Test FUNCTIONAL_BLOCKS covers A through P."""

    def test_covers_a_through_p(self):
        expected_letters = [chr(i) for i in range(ord("A"), ord("P") + 1)]
        for letter in expected_letters:
            assert letter in FUNCTIONAL_BLOCKS, f"Missing functional block '{letter}'"

    def test_exactly_16_blocks(self):
        assert len(FUNCTIONAL_BLOCKS) == 16

    def test_all_values_are_nonempty_strings(self):
        for letter, name in FUNCTIONAL_BLOCKS.items():
            assert isinstance(name, str)
            assert len(name) > 0, f"Block '{letter}' has empty name"

    def test_specific_block_names(self):
        assert FUNCTIONAL_BLOCKS["A"] == "Security"
        assert FUNCTIONAL_BLOCKS["B"] == "Provisioning"
        assert FUNCTIONAL_BLOCKS["C"] == "Authorization"
        assert FUNCTIONAL_BLOCKS["E"] == "Transactions"
        assert FUNCTIONAL_BLOCKS["K"] == "SmartCharging"
        assert FUNCTIONAL_BLOCKS["P"] == "DataTransfer"

    def test_no_duplicate_values(self):
        values = list(FUNCTIONAL_BLOCKS.values())
        assert len(values) == len(set(values)), "Duplicate functional block names found"
