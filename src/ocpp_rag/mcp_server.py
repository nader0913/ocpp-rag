"""MCP server exposing the OCPP RAG knowledge base as tools for LLM clients."""

import json

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from mcp.server.fastmcp import FastMCP

from .config import CHROMA_DIR, COLLECTION_NAME

mcp = FastMCP("ocpp-rag")


def get_collection():
    """Return the ChromaDB collection for querying."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = DefaultEmbeddingFunction()
    return client.get_collection(name=COLLECTION_NAME, embedding_function=ef)


def _build_where_clause(filters: dict) -> dict | None:
    """Build a ChromaDB where clause from a dict of field->value filters.

    Skips any entries where the value is None.  Returns None if no filters
    remain, a single-condition dict for one filter, or an ``$and`` clause for
    multiple filters.
    """
    conditions = [
        {field: value}
        for field, value in filters.items()
        if value is not None
    ]
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


@mcp.tool()
def search_ocpp(
    query: str,
    top_k: int = 10,
    ocpp_version: str | None = None,
    content_type: str | None = None,
) -> list[dict]:
    """Semantic search across all indexed OCPP documents.

    Search the OCPP 1.6 and 2.0.1 knowledge base for information about
    messages, use cases, requirements, device model components, JSON schemas,
    and more.

    Args:
        query: Natural-language search query (e.g. "how does remote start transaction work").
        top_k: Maximum number of results to return (default 10).
        ocpp_version: Optional filter - "1.6" or "2.0.1".
        content_type: Optional filter - one of "use_case", "requirements", "json_schema",
            "message_or_type", "component_variable", "block_intro", "general",
            "appendix", "datatypes_section", "enumerations_section", "messages_section".

    Returns:
        A list of matching documents, each with relevance score, heading,
        content, and metadata.
    """
    collection = get_collection()
    where = _build_where_clause({
        "ocpp_version": ocpp_version,
        "content_type": content_type,
    })
    kwargs: dict = {"query_texts": [query], "n_results": top_k}
    if where is not None:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i] or {}
        distance = results["distances"][0][i] if results.get("distances") else None
        # ChromaDB cosine distance is in [0, 2]; convert to a 0-1 relevance score.
        relevance = round(1.0 - (distance / 2.0), 4) if distance is not None else None

        output.append({
            "relevance": relevance,
            "heading": meta.get("heading"),
            "content": results["documents"][0][i],
            "doc_title": meta.get("doc_title"),
            "ocpp_version": meta.get("ocpp_version"),
            "content_type": meta.get("content_type"),
            "use_case_id": meta.get("use_case_id"),
            "functional_block": meta.get("functional_block"),
        })

    return output


@mcp.tool()
def get_use_case(use_case_id: str, ocpp_version: str = "2.0.1") -> dict | None:
    """Retrieve all chunks for a specific OCPP use case.

    Returns every chunk associated with the given use case identifier,
    including its description, sequence diagrams, requirements, and related
    messages.

    Args:
        use_case_id: The use case identifier, e.g. "A01", "B01", "K08", "E02".
        ocpp_version: OCPP version - defaults to "2.0.1".

    Returns:
        A dict with the use_case_id, ocpp_version, and a list of chunks
        (each with heading, content, content_type, and functional_block).
        Returns None if no chunks are found.
    """
    collection = get_collection()
    where = _build_where_clause({
        "use_case_id": use_case_id,
        "ocpp_version": ocpp_version,
    })
    if where is None:
        return None

    results = collection.get(where=where, include=["documents", "metadatas"])

    if not results["ids"]:
        return None

    chunks = []
    for i in range(len(results["ids"])):
        meta = results["metadatas"][i] or {}
        chunks.append({
            "heading": meta.get("heading"),
            "content": results["documents"][i],
            "content_type": meta.get("content_type"),
            "functional_block": meta.get("functional_block"),
        })

    return {
        "use_case_id": use_case_id,
        "ocpp_version": ocpp_version,
        "chunks": chunks,
    }


@mcp.tool()
def list_use_cases(
    ocpp_version: str | None = None,
    functional_block: str | None = None,
) -> list[dict]:
    """List all OCPP use cases with their names and functional blocks.

    Useful for discovering which use cases exist before fetching details
    with ``get_use_case``.

    Args:
        ocpp_version: Optional filter - "1.6" or "2.0.1".
        functional_block: Optional filter - e.g. "Security", "SmartCharging",
            "Transactions", "Authorization", "Provisioning".

    Returns:
        A sorted list of dicts, each with use_case_id, use_case_name,
        functional_block, and ocpp_version.
    """
    collection = get_collection()

    # We need to find chunks that have a use_case_id. Build filters.
    filters: dict = {"ocpp_version": ocpp_version, "functional_block": functional_block}
    where = _build_where_clause(
        {k: v for k, v in filters.items() if v is not None}
    )

    # ChromaDB get() doesn't support querying "field exists", so we fetch
    # broadly and filter in Python.
    kwargs: dict = {"include": ["metadatas"]}
    if where is not None:
        kwargs["where"] = where

    results = collection.get(**kwargs)

    seen = set()
    use_cases = []
    for meta in results["metadatas"]:
        uc_id = meta.get("use_case_id")
        if not uc_id:
            continue
        version = meta.get("ocpp_version")
        key = (uc_id, version)
        if key in seen:
            continue
        seen.add(key)
        use_cases.append({
            "use_case_id": uc_id,
            "use_case_name": meta.get("use_case_name", ""),
            "functional_block": meta.get("functional_block", ""),
            "ocpp_version": version,
        })

    use_cases.sort(key=lambda x: (x["ocpp_version"] or "", x["use_case_id"]))
    return use_cases


@mcp.tool()
def get_message_schema(message_name: str) -> dict | None:
    """Look up the JSON schema for a specific OCPP 2.0.1 message.

    Returns the schema definition including all properties, types, and
    constraints for the given message.

    Args:
        message_name: The message name, e.g. "BootNotificationRequest",
            "AuthorizeResponse", "TransactionEventRequest".

    Returns:
        A dict with the message name, heading, content (rendered schema),
        and direction (Request/Response). Returns None if not found.
    """
    collection = get_collection()
    where = _build_where_clause({
        "content_type": "json_schema",
        "message_name": message_name,
    })
    if where is None:
        return None

    results = collection.get(where=where, include=["documents", "metadatas"])

    if not results["ids"]:
        return None

    # Combine all parts (schema chunks may be split across multiple chunks).
    parts = []
    direction = None
    heading = None
    for i in range(len(results["ids"])):
        meta = results["metadatas"][i] or {}
        parts.append({
            "chunk_part": meta.get("chunk_part", 1),
            "content": results["documents"][i],
        })
        if direction is None:
            direction = meta.get("message_direction")
        if heading is None:
            heading = meta.get("heading")

    parts.sort(key=lambda p: p["chunk_part"])
    combined_content = "\n".join(p["content"] for p in parts)

    return {
        "message_name": message_name,
        "heading": heading,
        "content": combined_content,
        "direction": direction,
    }


@mcp.tool()
def get_component_variable(
    component: str | None = None,
    variable: str | None = None,
) -> list[dict]:
    """Look up OCPP 2.0.1 device model components and variables.

    Search the appendices for device model component and variable definitions,
    optionally filtered by component or variable name.

    Args:
        component: Optional component name to filter by (e.g. "EVSE", "Connector",
            "ChargingStation").
        variable: Optional variable name to search for in content.

    Returns:
        A list of matching chunks, each with heading, content, and
        component_name.
    """
    collection = get_collection()

    filters: dict = {"content_type": "component_variable"}
    if component is not None:
        filters["component_name"] = component
    where = _build_where_clause(filters)

    results = collection.get(where=where, include=["documents", "metadatas"])

    output = []
    for i in range(len(results["ids"])):
        meta = results["metadatas"][i] or {}
        content = results["documents"][i]

        # If a variable name is specified, only include chunks that mention it.
        if variable is not None and variable.lower() not in content.lower():
            continue

        output.append({
            "heading": meta.get("heading"),
            "content": content,
            "component_name": meta.get("component_name"),
        })

    return output


@mcp.tool()
def list_documents() -> list[dict]:
    """List all documents indexed in the OCPP knowledge base.

    Returns a summary of every document with its ID, title, OCPP version,
    and the number of chunks it was split into.

    Returns:
        A list of dicts, each with doc_id, doc_title, ocpp_version, and
        chunk_count.
    """
    collection = get_collection()
    results = collection.get(include=["metadatas"])

    doc_info: dict[str, dict] = {}
    for meta in results["metadatas"]:
        doc_id = meta.get("doc_id", "unknown")
        if doc_id not in doc_info:
            doc_info[doc_id] = {
                "doc_id": doc_id,
                "doc_title": meta.get("doc_title", ""),
                "ocpp_version": meta.get("ocpp_version"),
                "chunk_count": 0,
            }
        doc_info[doc_id]["chunk_count"] += 1

    return sorted(doc_info.values(), key=lambda d: d["doc_id"])


@mcp.tool()
def compare_versions(topic: str) -> dict:
    """Compare how a topic is covered in OCPP 1.6 vs OCPP 2.0.1.

    Performs the same semantic search against both OCPP versions and returns
    the results side by side, making it easy to see differences in how a
    feature or concept is handled across versions.

    Args:
        topic: The topic to compare (e.g. "smart charging", "authorization",
            "boot notification", "firmware update").

    Returns:
        A dict with the query, v16_results (OCPP 1.6 matches), and
        v201_results (OCPP 2.0.1 matches), each containing up to 5 results.
    """
    v16_results = search_ocpp(query=topic, top_k=5, ocpp_version="1.6")
    v201_results = search_ocpp(query=topic, top_k=5, ocpp_version="2.0.1")

    return {
        "query": topic,
        "v16_results": v16_results,
        "v201_results": v201_results,
    }


if __name__ == "__main__":
    mcp.run()
