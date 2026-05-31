"""Tests for ocpp_rag.mcp_server module (tool functions tested directly)."""

import json
from unittest.mock import patch, MagicMock

import pytest

from ocpp_rag.mcp_server import (
    search_ocpp,
    get_use_case,
    list_use_cases,
    get_message_schema,
    get_component_variable,
    list_documents,
    compare_versions,
    _build_where_clause,
)


class MockCollection:
    """A mock ChromaDB collection for testing MCP server tools."""

    def __init__(self, chunks):
        self._chunks = chunks
        self._ids = [f"chunk_{i}" for i in range(len(chunks))]
        self._documents = [c["content"] for c in chunks]
        self._metadatas = [c["metadata"] for c in chunks]

    def query(self, query_texts=None, n_results=10, where=None, **kwargs):
        """Simulate ChromaDB query - returns results matching where filters."""
        indices = list(range(len(self._chunks)))

        if where:
            indices = self._filter_indices(indices, where)

        indices = indices[:n_results]

        return {
            "ids": [[self._ids[i] for i in indices]],
            "documents": [[self._documents[i] for i in indices]],
            "metadatas": [[self._metadatas[i] for i in indices]],
            "distances": [[0.1 * (j + 1) for j in range(len(indices))]],
        }

    def get(self, where=None, include=None, **kwargs):
        """Simulate ChromaDB get - returns all matching documents."""
        indices = list(range(len(self._chunks)))

        if where:
            indices = self._filter_indices(indices, where)

        result = {"ids": [self._ids[i] for i in indices]}
        if include and "documents" in include:
            result["documents"] = [self._documents[i] for i in indices]
        if include and "metadatas" in include:
            result["metadatas"] = [self._metadatas[i] for i in indices]
        else:
            result["metadatas"] = [self._metadatas[i] for i in indices]

        return result

    def _filter_indices(self, indices, where):
        """Apply ChromaDB-style where filters."""
        if "$and" in where:
            for condition in where["$and"]:
                indices = self._filter_indices(indices, condition)
            return indices

        for key, value in where.items():
            if key.startswith("$"):
                continue
            indices = [
                i for i in indices
                if self._metadatas[i].get(key) == value
            ]
        return indices


@pytest.fixture
def mock_collection(sample_chunks):
    """Create a mock collection from sample_chunks."""
    return MockCollection(sample_chunks)


@pytest.fixture
def patch_get_collection(mock_collection):
    """Patch get_collection to return the mock."""
    with patch("ocpp_rag.mcp_server.get_collection", return_value=mock_collection):
        yield mock_collection


class TestBuildWhereClause:
    """Test _build_where_clause helper."""

    def test_empty_filters(self):
        result = _build_where_clause({})
        assert result is None

    def test_all_none_values(self):
        result = _build_where_clause({"a": None, "b": None})
        assert result is None

    def test_single_filter(self):
        result = _build_where_clause({"ocpp_version": "2.0.1", "other": None})
        assert result == {"ocpp_version": "2.0.1"}

    def test_multiple_filters(self):
        result = _build_where_clause({"ocpp_version": "2.0.1", "content_type": "use_case"})
        assert result == {"$and": [{"ocpp_version": "2.0.1"}, {"content_type": "use_case"}]}


class TestSearchOcpp:
    """Test search_ocpp tool function."""

    def test_basic_search(self, patch_get_collection):
        results = search_ocpp(query="boot notification")
        assert isinstance(results, list)
        assert len(results) > 0

    def test_result_structure(self, patch_get_collection):
        results = search_ocpp(query="boot notification")
        for r in results:
            assert "relevance" in r
            assert "heading" in r
            assert "content" in r
            assert "doc_title" in r
            assert "ocpp_version" in r
            assert "content_type" in r

    def test_relevance_score_range(self, patch_get_collection):
        results = search_ocpp(query="boot")
        for r in results:
            assert 0 <= r["relevance"] <= 1.0

    def test_version_filter(self, patch_get_collection):
        results = search_ocpp(query="boot", ocpp_version="2.0.1")
        for r in results:
            assert r["ocpp_version"] == "2.0.1"

    def test_content_type_filter(self, patch_get_collection):
        results = search_ocpp(query="boot", content_type="use_case")
        for r in results:
            assert r["content_type"] == "use_case"

    def test_top_k_limits_results(self, patch_get_collection):
        results = search_ocpp(query="boot", top_k=2)
        assert len(results) <= 2

    def test_combined_filters(self, patch_get_collection):
        results = search_ocpp(query="boot", ocpp_version="2.0.1", content_type="use_case")
        for r in results:
            assert r["ocpp_version"] == "2.0.1"
            assert r["content_type"] == "use_case"


class TestGetUseCase:
    """Test get_use_case tool function."""

    def test_existing_use_case(self, patch_get_collection):
        result = get_use_case(use_case_id="B01", ocpp_version="2.0.1")
        assert result is not None
        assert result["use_case_id"] == "B01"
        assert result["ocpp_version"] == "2.0.1"
        assert "chunks" in result
        assert len(result["chunks"]) > 0

    def test_nonexistent_use_case(self, patch_get_collection):
        result = get_use_case(use_case_id="Z99", ocpp_version="2.0.1")
        assert result is None

    def test_chunk_content_structure(self, patch_get_collection):
        result = get_use_case(use_case_id="B01", ocpp_version="2.0.1")
        if result:
            for chunk in result["chunks"]:
                assert "heading" in chunk
                assert "content" in chunk
                assert "content_type" in chunk


class TestListUseCases:
    """Test list_use_cases tool function."""

    def test_returns_sorted_list(self, patch_get_collection):
        results = list_use_cases()
        assert isinstance(results, list)
        # Verify sorted by (ocpp_version, use_case_id)
        for i in range(len(results) - 1):
            curr = (results[i]["ocpp_version"] or "", results[i]["use_case_id"])
            next_ = (results[i + 1]["ocpp_version"] or "", results[i + 1]["use_case_id"])
            assert curr <= next_

    def test_result_structure(self, patch_get_collection):
        results = list_use_cases()
        for r in results:
            assert "use_case_id" in r
            assert "use_case_name" in r
            assert "functional_block" in r
            assert "ocpp_version" in r

    def test_unique_ids(self, patch_get_collection):
        results = list_use_cases()
        keys = [(r["use_case_id"], r["ocpp_version"]) for r in results]
        assert len(keys) == len(set(keys)), "Duplicate use case IDs found"

    def test_version_filter(self, patch_get_collection):
        results = list_use_cases(ocpp_version="2.0.1")
        for r in results:
            assert r["ocpp_version"] == "2.0.1"


class TestGetMessageSchema:
    """Test get_message_schema tool function."""

    def test_existing_message(self, patch_get_collection):
        result = get_message_schema(message_name="BootNotificationRequest")
        if result:
            assert result["message_name"] == "BootNotificationRequest"
            assert "content" in result
            assert "direction" in result

    def test_nonexistent_message(self, patch_get_collection):
        result = get_message_schema(message_name="NonExistentMessage")
        assert result is None


class TestGetComponentVariable:
    """Test get_component_variable tool function."""

    def test_no_filters(self, patch_get_collection):
        # This queries for content_type == "component_variable" which none of our
        # sample_chunks have, so it should return empty
        results = get_component_variable()
        assert isinstance(results, list)

    def test_with_component_filter(self, patch_get_collection):
        results = get_component_variable(component="EVSE")
        assert isinstance(results, list)


class TestListDocuments:
    """Test list_documents tool function."""

    def test_returns_list(self, patch_get_collection):
        results = list_documents()
        assert isinstance(results, list)
        assert len(results) > 0

    def test_result_structure(self, patch_get_collection):
        results = list_documents()
        for r in results:
            assert "doc_id" in r
            assert "doc_title" in r
            assert "ocpp_version" in r
            assert "chunk_count" in r
            assert r["chunk_count"] > 0

    def test_sorted_by_doc_id(self, patch_get_collection):
        results = list_documents()
        doc_ids = [r["doc_id"] for r in results]
        assert doc_ids == sorted(doc_ids)

    def test_chunk_counts_correct(self, patch_get_collection, sample_chunks):
        results = list_documents()
        total_chunks = sum(r["chunk_count"] for r in results)
        assert total_chunks == len(sample_chunks)


class TestCompareVersions:
    """Test compare_versions tool function."""

    def test_returns_both_versions(self, patch_get_collection):
        result = compare_versions(topic="authorization")
        assert "query" in result
        assert result["query"] == "authorization"
        assert "v16_results" in result
        assert "v201_results" in result

    def test_v16_results_are_v16(self, patch_get_collection):
        result = compare_versions(topic="boot")
        for r in result["v16_results"]:
            assert r["ocpp_version"] == "1.6"

    def test_v201_results_are_v201(self, patch_get_collection):
        result = compare_versions(topic="boot")
        for r in result["v201_results"]:
            assert r["ocpp_version"] == "2.0.1"
