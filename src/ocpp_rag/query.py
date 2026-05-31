import os
import sys
import json
import argparse

import anthropic
import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
from dotenv import load_dotenv

from .config import CHROMA_DIR, COLLECTION_NAME

load_dotenv()

MODEL = "claude-sonnet-4-20250514"
TOP_K = 12

SYSTEM_PROMPT = """You are an expert on EV charging protocols, specifically OCPP (Open Charge Point Protocol) versions 1.6 and 2.0.1, as well as related standards like OCPI, ISO 15118, and Plug & Charge.

You have access to retrieved context from official specification documents. Use ONLY the provided context to answer questions. If the context doesn't contain enough information, say so clearly.

When referencing specific requirements, use the exact requirement IDs (e.g. A01.FR.01, E02.FR.03).
When referencing use cases, use the exact IDs (e.g. B01 - Cold Boot Charging Station).
When referencing messages, use exact names (e.g. BootNotificationRequest).
Always mention which OCPP version (1.6 or 2.0.1) you're referring to.

Be precise and technical. Quote relevant requirement text when it helps clarify."""


def get_collection():
    """Get the ChromaDB collection for querying."""
    if not CHROMA_DIR.exists():
        print(f"[ERROR] ChromaDB directory not found: {CHROMA_DIR}")
        print("Run `python -m ocpp_rag.index` first to build the index.")
        sys.exit(1)

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = DefaultEmbeddingFunction()
    try:
        return client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
        )
    except Exception as e:
        print(f"[ERROR] Could not load collection '{COLLECTION_NAME}': {e}")
        print("Run `python -m ocpp_rag.index` first to build the index.")
        sys.exit(1)


def retrieve(collection, question, n_results=TOP_K, filters=None):
    """Query ChromaDB and return list of (doc, metadata, distance) tuples.

    Args:
        collection: ChromaDB collection.
        question: The query string.
        n_results: Number of results to retrieve.
        filters: Optional dict with keys like 'ocpp_version' or 'content_type'
                 to build a ChromaDB where filter.

    Returns:
        List of (document_text, metadata_dict, distance_float) tuples,
        ordered by relevance (lowest distance first).
    """
    query_kwargs = {
        "query_texts": [question],
        "n_results": n_results,
    }

    if filters:
        where_clauses = []
        if "ocpp_version" in filters:
            where_clauses.append({"ocpp_version": filters["ocpp_version"]})
        if "content_type" in filters:
            where_clauses.append({"content_type": filters["content_type"]})

        if len(where_clauses) == 1:
            query_kwargs["where"] = where_clauses[0]
        elif len(where_clauses) > 1:
            query_kwargs["where"] = {"$and": where_clauses}

    results = collection.query(**query_kwargs)

    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    return list(zip(docs, metas, distances))


def format_context(results):
    """Format retrieved chunks into a context string for the LLM.

    Args:
        results: List of (doc, metadata, distance) tuples from retrieve().

    Returns:
        Formatted string with all chunks and their metadata.
    """
    parts = []
    for i, (doc, meta, distance) in enumerate(results, 1):
        relevance = max(0.0, 1.0 - distance)  # cosine distance -> similarity
        header_lines = [f"--- Context Chunk {i} ---"]
        header_lines.append(f"Document: {meta.get('doc_title', 'Unknown')}")
        header_lines.append(f"OCPP Version: {meta.get('ocpp_version', 'N/A')}")
        header_lines.append(f"Content Type: {meta.get('content_type', 'N/A')}")

        if meta.get("use_case_id"):
            header_lines.append(f"Use Case: {meta['use_case_id']}")
        if meta.get("functional_block"):
            header_lines.append(f"Functional Block: {meta['functional_block']}")

        header_lines.append(f"Relevance: {relevance:.2%}")
        header_lines.append("")
        header_lines.append(doc)
        header_lines.append("")

        parts.append("\n".join(header_lines))

    return "\n".join(parts)


def ask(question, collection=None, stream=True, filters=None):
    """Ask a question using RAG: retrieve context then query Claude.

    Args:
        question: The user's question.
        collection: ChromaDB collection (fetched if None).
        stream: Whether to stream the response.
        filters: Optional filters for retrieval.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY environment variable is not set.")
        print("Set it in your .env file or export it in your shell.")
        return

    if collection is None:
        collection = get_collection()

    results = retrieve(collection, question, filters=filters)

    if not results:
        print("[WARNING] No results found in the knowledge base.")
        return

    context = format_context(results)

    user_message = f"""Context from OCPP specification documents:

{context}

Question: {question}"""

    client = anthropic.Anthropic(api_key=api_key)

    print()
    if stream:
        with client.messages.stream(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as response:
            for text in response.text_stream:
                print(text, end="", flush=True)
    else:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        print(response.content[0].text)

    # Print sources
    print("\n")
    print("--- Sources ---")
    seen = set()
    for _, meta, distance in results:
        relevance = max(0.0, 1.0 - distance)
        doc_key = (
            meta.get("doc_title", "Unknown"),
            meta.get("ocpp_version", "N/A"),
            meta.get("content_type", "N/A"),
        )
        if doc_key not in seen:
            seen.add(doc_key)
            parts = [f"  - {doc_key[0]}"]
            parts.append(f"(v{doc_key[1]})")
            parts.append(f"[{doc_key[2]}]")
            parts.append(f"relevance={relevance:.2%}")
            print(" ".join(parts))


def interactive(collection):
    """Run an interactive REPL for querying the OCPP knowledge base."""
    print("OCPP RAG - Interactive Query")
    print("=" * 40)
    print("Commands:")
    print("  quit/exit/q   - Exit")
    print("  search: <q>   - Raw search results (no LLM)")
    print("  v16: <q>      - Filter to OCPP 1.6 only")
    print("  v201: <q>     - Filter to OCPP 2.0.1 only")
    print()

    while True:
        try:
            question = input("Q: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye.")
            break

        if not question:
            continue

        if question.lower() in ("quit", "exit", "q"):
            print("Goodbye.")
            break

        # Raw search mode
        if question.lower().startswith("search:"):
            query = question[7:].strip()
            if not query:
                print("[INFO] Usage: search: <your query>")
                continue
            results = retrieve(collection, query)
            for i, (doc, meta, distance) in enumerate(results, 1):
                relevance = max(0.0, 1.0 - distance)
                print(f"\n--- Result {i} (relevance={relevance:.2%}) ---")
                print(f"  Doc: {meta.get('doc_title', 'Unknown')}")
                print(f"  Version: {meta.get('ocpp_version', 'N/A')}")
                print(f"  Type: {meta.get('content_type', 'N/A')}")
                if meta.get("use_case_id"):
                    print(f"  Use Case: {meta['use_case_id']}")
                if meta.get("functional_block"):
                    print(f"  Block: {meta['functional_block']}")
                # Show a preview of the content
                preview = doc[:300].replace("\n", " ")
                if len(doc) > 300:
                    preview += "..."
                print(f"  Content: {preview}")
            print()
            continue

        # Version-filtered queries
        filters = None
        if question.lower().startswith("v16:"):
            question = question[4:].strip()
            filters = {"ocpp_version": "1.6"}
            if not question:
                print("[INFO] Usage: v16: <your query>")
                continue
        elif question.lower().startswith("v201:"):
            question = question[5:].strip()
            filters = {"ocpp_version": "2.0.1"}
            if not question:
                print("[INFO] Usage: v201: <your query>")
                continue

        try:
            ask(question, collection=collection, filters=filters)
        except KeyboardInterrupt:
            print("\n[Interrupted]")
        except anthropic.APIError as e:
            print(f"\n[API Error] {e}")

        print()


def main():
    parser = argparse.ArgumentParser(
        description="Query the OCPP RAG knowledge base",
        epilog=(
            "Examples:\n"
            "  python -m ocpp_rag.query                              # interactive mode\n"
            '  python -m ocpp_rag.query "What is cold boot?"         # single question\n'
            '  python -m ocpp_rag.query --version 1.6 "Authorization"  # version filter\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="Question to ask (omit for interactive mode)",
    )
    parser.add_argument(
        "--version",
        choices=["1.6", "2.0.1"],
        default=None,
        help="Filter results to a specific OCPP version",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        help=f"Number of chunks to retrieve (default: {TOP_K})",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output",
    )
    args = parser.parse_args()

    # Override global TOP_K if specified
    global TOP_K
    TOP_K = args.top_k

    collection = get_collection()

    filters = None
    if args.version:
        filters = {"ocpp_version": args.version}

    if args.question:
        # Single-shot mode
        ask(args.question, collection=collection, stream=not args.no_stream, filters=filters)
        print()
    else:
        # Interactive mode
        interactive(collection)


if __name__ == "__main__":
    main()
