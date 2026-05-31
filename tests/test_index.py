"""Tests for ocpp_rag.index module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from ocpp_rag.index import _flatten_metadata, build_index, get_collection


class TestFlattenMetadata:
    """Test _flatten_metadata converts values for ChromaDB compatibility."""

    def test_strings_pass_through(self):
        meta = {"key": "value", "title": "OCPP 2.0.1"}
        result = _flatten_metadata(meta)
        assert result == {"key": "value", "title": "OCPP 2.0.1"}

    def test_integers_pass_through(self):
        meta = {"page": 42, "count": 0}
        result = _flatten_metadata(meta)
        assert result == {"page": 42, "count": 0}

    def test_floats_pass_through(self):
        meta = {"score": 0.95}
        result = _flatten_metadata(meta)
        assert result == {"score": 0.95}

    def test_booleans_pass_through(self):
        meta = {"required": True, "optional": False}
        result = _flatten_metadata(meta)
        assert result == {"required": True, "optional": False}

    def test_none_values_removed(self):
        meta = {"key": "value", "empty": None, "also_empty": None}
        result = _flatten_metadata(meta)
        assert "empty" not in result
        assert "also_empty" not in result
        assert result == {"key": "value"}

    def test_lists_become_comma_separated(self):
        meta = {"refs": ["A01", "B02", "K08"]}
        result = _flatten_metadata(meta)
        assert result["refs"] == "A01, B02, K08"

    def test_lists_of_ints(self):
        meta = {"pages": [1, 5, 10]}
        result = _flatten_metadata(meta)
        assert result["pages"] == "1, 5, 10"

    def test_other_types_become_string(self):
        meta = {"path": Path("/some/path")}
        result = _flatten_metadata(meta)
        assert isinstance(result["path"], str)

    def test_empty_dict(self):
        result = _flatten_metadata({})
        assert result == {}

    def test_mixed_values(self):
        meta = {
            "doc_id": "ocpp201_part2",
            "page": 42,
            "ocpp_version": "2.0.1",
            "tags": ["security", "provisioning"],
            "nullable": None,
            "required": True,
        }
        result = _flatten_metadata(meta)
        assert result == {
            "doc_id": "ocpp201_part2",
            "page": 42,
            "ocpp_version": "2.0.1",
            "tags": "security, provisioning",
            "required": True,
        }


class TestBuildIndexAndQuery:
    """Test building an index and querying it with ChromaDB."""

    def test_build_and_query(self, tmp_path, sample_chunks):
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(sample_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_collection"):
            build_index(chunks_path=chunks_file, force=True)

        # Now query the index
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_collection", embedding_function=ef)

        assert collection.count() == len(sample_chunks)

        # Test a search query
        results = collection.query(
            query_texts=["boot notification"],
            n_results=2,
        )
        assert len(results["ids"][0]) > 0
        # Should find BootNotification-related chunks
        found_docs = results["documents"][0]
        assert any("BootNotification" in doc for doc in found_docs)

    def test_build_index_creates_correct_count(self, tmp_path, sample_chunks):
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(sample_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_count"):
            build_index(chunks_path=chunks_file, force=True)

        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_count", embedding_function=ef)
        assert collection.count() == 4

    def test_build_index_skips_existing_without_force(self, tmp_path, sample_chunks):
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(sample_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_skip"):
            # First build
            build_index(chunks_path=chunks_file, force=True)
            # Second build without force should skip
            build_index(chunks_path=chunks_file, force=False)

        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_skip", embedding_function=ef)
        # Should still have original count (not doubled)
        assert collection.count() == 4


class TestVersionFilter:
    """Test filtering by OCPP version in queries."""

    def test_version_filter_201(self, tmp_path, sample_chunks):
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(sample_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_version"):
            build_index(chunks_path=chunks_file, force=True)

        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_version", embedding_function=ef)

        # Query with version filter for 2.0.1
        results = collection.query(
            query_texts=["boot"],
            n_results=10,
            where={"ocpp_version": "2.0.1"},
        )
        for meta in results["metadatas"][0]:
            assert meta["ocpp_version"] == "2.0.1"

    def test_version_filter_16(self, tmp_path, sample_chunks):
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(sample_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_version_16"):
            build_index(chunks_path=chunks_file, force=True)

        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_version_16", embedding_function=ef)

        # Query with version filter for 1.6
        results = collection.query(
            query_texts=["WebSocket"],
            n_results=10,
            where={"ocpp_version": "1.6"},
        )
        assert len(results["ids"][0]) > 0
        for meta in results["metadatas"][0]:
            assert meta["ocpp_version"] == "1.6"

    def test_metadata_stored_correctly(self, tmp_path, sample_chunks):
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(sample_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_meta"):
            build_index(chunks_path=chunks_file, force=True)

        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_meta", embedding_function=ef)

        # Get all entries and verify metadata
        all_results = collection.get(include=["metadatas"])
        for meta in all_results["metadatas"]:
            assert "doc_id" in meta
            assert "content_type" in meta
            # None values should not be present (filtered by _flatten_metadata)
            for key, value in meta.items():
                assert value is not None
