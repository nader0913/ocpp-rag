"""End-to-end integration tests for the OCPP RAG pipeline."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from ocpp_rag.chunk import chunk_markdown, chunk_json_schemas, chunk_appendices
from ocpp_rag.index import build_index, _flatten_metadata


@pytest.mark.integration
class TestEndToEndPipeline:
    """Integration test: create markdown, chunk, index, query."""

    def test_full_pipeline(self, tmp_path):
        """End-to-end test: markdown -> chunks -> index -> query."""
        # Step 1: Create a sample markdown file
        markdown_content = """\
[PAGE 1]

# A. Security

This section covers security use cases for OCPP 2.0.1.
Security is critical for the communication between Charging Stations and the CSMS.
It covers authentication, authorization, and encrypted communication channels.
All security-related use cases are identified by the letter A prefix.

## A01 - Update Charging Station Password for HTTP Basic Authentication

| No. | Type | Description |
|---|---|---|
| 1 | Name | Update Charging Station Password for HTTP Basic Authentication |
| 2 | ID | A01 |
| 3 | Objective | Allow the CSMS to change the HTTP Basic Auth password |

The CSMS can update the password used by the Charging Station for HTTP Basic
Authentication. The Charging Station SHALL accept a SetVariablesRequest that sets
the BasicAuthPassword variable. After a successful update, the Charging Station
SHALL use the new password for all subsequent HTTP connections to the CSMS.

See also B02 for provisioning key management.

[PAGE 2]

## A01 - Update Charging Station Password for HTTP Basic Authentication - Requirements

| ID | Precondition | Requirement |
|---|---|---|
| A01.FR.01 | When CSMS sends SetVariablesRequest with BasicAuthPassword | The Charging Station SHALL store the new password securely |
| A01.FR.02 | After password update | The Charging Station SHALL use the new password for the next connection |
| A01.FR.03 | If password policy is not met | The Charging Station SHALL respond with SetVariablesResponse status Rejected |

## A02 - Certificate-Based Authentication

| No. | Type | Description |
|---|---|---|
| 1 | Name | Certificate-Based Authentication |
| 2 | ID | A02 |

The Charging Station uses TLS client certificates for mutual authentication.
The Charging Station SHALL present its certificate during the TLS handshake.
This is the preferred authentication method in OCPP 2.0.1.

# B. Provisioning

This functional block handles the provisioning of Charging Stations within an OCPP network.
Provisioning covers initial boot, configuration management, and variable handling.
All provisioning use cases are identified by the letter B prefix and are essential for
setting up and maintaining Charging Stations connected to a CSMS.

## B01 - Cold Boot Charging Station

| No. | Type | Description |
|---|---|---|
| 1 | Name | Cold Boot Charging Station |
| 2 | ID | B01 |

After power-up, the Charging Station SHALL send a BootNotificationRequest
message to the CSMS. The CSMS responds with BootNotificationResponse containing
the current time and a heartbeat interval.
"""
        md_path = tmp_path / "parsed" / "ocpp201_part2.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown_content)

        # Step 2: Chunk the markdown
        doc_info = {
            "title": "OCPP 2.0.1 Part 2 - Specification",
            "ocpp_version": "2.0.1",
        }
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        assert len(chunks) > 0
        # Verify we got different content types
        content_types = {c["metadata"]["content_type"] for c in chunks}
        assert "use_case" in content_types
        assert "requirements" in content_types
        assert "block_intro" in content_types

        # Step 3: Save chunks and build index
        chunks_file = tmp_path / "chunks" / "_all_chunks.json"
        chunks_file.parent.mkdir(parents=True, exist_ok=True)
        chunks_file.write_text(json.dumps(chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_e2e"):
            build_index(chunks_path=chunks_file, force=True)

        # Step 4: Query and verify results
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_e2e", embedding_function=ef)

        assert collection.count() == len(chunks)

        # Query for password-related content
        results = collection.query(
            query_texts=["How does password update work in OCPP?"],
            n_results=3,
        )
        assert len(results["ids"][0]) > 0
        # Top results should relate to A01
        top_meta = results["metadatas"][0][0]
        assert top_meta.get("use_case_id") == "A01" or "password" in results["documents"][0][0].lower()

        # Query for boot notification
        results = collection.query(
            query_texts=["boot notification cold start"],
            n_results=3,
        )
        assert len(results["ids"][0]) > 0
        found_boot = any(
            "BootNotification" in doc or "Cold Boot" in doc
            for doc in results["documents"][0]
        )
        assert found_boot, "Should find BootNotification-related content"

        # Query with version filter
        results = collection.query(
            query_texts=["authentication"],
            n_results=5,
            where={"ocpp_version": "2.0.1"},
        )
        for meta in results["metadatas"][0]:
            assert meta["ocpp_version"] == "2.0.1"

    def test_pipeline_with_schemas(self, tmp_path):
        """Test pipeline including JSON schema chunks."""
        # Create schema data
        schemas = [
            {
                "message_name": "SetVariablesRequest",
                "direction": "Request",
                "schema": {
                    "type": "object",
                    "properties": {
                        "setVariableData": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/SetVariableDataType"},
                        },
                    },
                    "required": ["setVariableData"],
                    "definitions": {
                        "SetVariableDataType": {
                            "type": "object",
                            "description": "Data to set a variable.",
                        },
                    },
                },
                "properties": [
                    {
                        "name": "setVariableData",
                        "type": "array<SetVariableDataType>",
                        "description": "List of variable data to set",
                        "required": True,
                    },
                ],
            },
            {
                "message_name": "SetVariablesResponse",
                "direction": "Response",
                "schema": {
                    "type": "object",
                    "properties": {
                        "setVariableResult": {
                            "type": "array",
                            "items": {"$ref": "#/definitions/SetVariableResultType"},
                        },
                    },
                    "required": ["setVariableResult"],
                    "definitions": {
                        "SetVariableResultType": {
                            "type": "object",
                            "description": "Result of setting a variable.",
                        },
                    },
                },
                "properties": [
                    {
                        "name": "setVariableResult",
                        "type": "array<SetVariableResultType>",
                        "description": "List of variable setting results",
                        "required": True,
                    },
                ],
            },
        ]

        schemas_path = tmp_path / "schemas" / "all_schemas.json"
        schemas_path.parent.mkdir(parents=True, exist_ok=True)
        schemas_path.write_text(json.dumps(schemas))

        # Chunk schemas
        schema_chunks = chunk_json_schemas(schemas_path)
        assert len(schema_chunks) >= 2

        # Build index
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(schema_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_schemas"):
            build_index(chunks_path=chunks_file, force=True)

        # Query for SetVariables
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_schemas", embedding_function=ef)

        results = collection.query(
            query_texts=["set variables"],
            n_results=5,
        )
        assert len(results["ids"][0]) > 0
        found_set_vars = any(
            "SetVariables" in doc
            for doc in results["documents"][0]
        )
        assert found_set_vars

    def test_pipeline_with_appendices(self, tmp_path):
        """Test pipeline including appendix chunks."""
        appendices_data = {
            "components": [
                {"component": "EVSE", "description": "Electric Vehicle Supply Equipment"},
                {"component": "Connector", "description": "Physical connector on EVSE"},
            ],
            "variables": [
                {
                    "name": "AvailabilityState",
                    "data_type": "OptionList",
                    "unit": "",
                    "description": "Current availability state of the component",
                    "component": "EVSE",
                },
                {
                    "name": "Power",
                    "data_type": "decimal",
                    "unit": "W",
                    "description": "Maximum power output",
                    "component": "EVSE",
                },
            ],
            "reason_codes": [
                {
                    "group": "Transaction",
                    "reason_code": "EVDisconnected",
                    "description": "EV was physically disconnected",
                    "typically_used_for": "Normal end of charging",
                },
            ],
            "security_events": [],
            "units_of_measure": [
                {"unit": "W", "description": "Watt"},
                {"unit": "kW", "description": "Kilowatt"},
            ],
        }

        appendices_path = tmp_path / "appendices" / "all_appendices.json"
        appendices_path.parent.mkdir(parents=True, exist_ok=True)
        appendices_path.write_text(json.dumps(appendices_data))

        # Chunk appendices
        appendix_chunks = chunk_appendices(appendices_path)
        assert len(appendix_chunks) > 0

        # Build index
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(appendix_chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_appendices"):
            build_index(chunks_path=chunks_file, force=True)

        # Query for EVSE component
        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_appendices", embedding_function=ef)

        results = collection.query(
            query_texts=["EVSE variables and power"],
            n_results=5,
        )
        assert len(results["ids"][0]) > 0
        found_evse = any("EVSE" in doc for doc in results["documents"][0])
        assert found_evse

    def test_metadata_preserved_through_pipeline(self, tmp_path):
        """Verify metadata integrity through the full pipeline."""
        markdown_content = """\
# E. Transactions

## E02 - Start Transaction

| No. | Type | Description |
|---|---|---|
| 1 | Name | Start Transaction |
| 2 | ID | E02 |

When an EV connects and authorization is given, the Charging Station SHALL
start a transaction by sending TransactionEventRequest with eventType = Started.
The CSMS responds with TransactionEventResponse. See C01 for authorization details.
"""
        md_path = tmp_path / "test.md"
        md_path.write_text(markdown_content)

        doc_info = {"title": "OCPP 2.0.1 Part 2", "ocpp_version": "2.0.1"}
        chunks = chunk_markdown(md_path, "ocpp201_part2", doc_info)

        # Save and index
        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(json.dumps(chunks))

        chroma_dir = tmp_path / "chroma_db"
        chroma_dir.mkdir()

        with patch("ocpp_rag.index.CHROMA_DIR", chroma_dir), \
             patch("ocpp_rag.index.COLLECTION_NAME", "test_metadata"):
            build_index(chunks_path=chunks_file, force=True)

        client = chromadb.PersistentClient(path=str(chroma_dir))
        ef = DefaultEmbeddingFunction()
        collection = client.get_collection(name="test_metadata", embedding_function=ef)

        # Get all entries and verify metadata is preserved
        all_results = collection.get(include=["metadatas", "documents"])

        for meta in all_results["metadatas"]:
            assert meta["doc_id"] == "ocpp201_part2"
            assert meta["ocpp_version"] == "2.0.1"
            # All values should be ChromaDB-compatible (no None, no nested dicts)
            for key, value in meta.items():
                assert isinstance(value, (str, int, float, bool)), (
                    f"Metadata key '{key}' has invalid type: {type(value)}"
                )
