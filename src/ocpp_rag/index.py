import json
import argparse
from collections import Counter
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

from .config import CHROMA_DIR, COLLECTION_NAME, CHUNKS_DIR

BATCH_SIZE = 100


def _flatten_metadata(meta):
    """Flatten metadata so all values are str/int/float/bool for ChromaDB."""
    flat = {}
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            flat[key] = value
        elif isinstance(value, list):
            flat[key] = ", ".join(str(v) for v in value)
        else:
            flat[key] = str(value)
    return flat


def build_index(chunks_path=None, force=False):
    """Build ChromaDB vector index from chunks JSON."""
    if chunks_path is None:
        chunks_path = CHUNKS_DIR / "_all_chunks.json"
    else:
        chunks_path = Path(chunks_path)

    if not chunks_path.exists():
        print(f"[ERROR] Chunks file not found: {chunks_path}")
        print("Run `python -m ocpp_rag.chunk` first.")
        return

    print(f"[INDEX] Loading chunks from {chunks_path}...")
    with open(chunks_path) as f:
        chunks = json.load(f)
    print(f"  -> {len(chunks)} chunks loaded")

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = DefaultEmbeddingFunction()

    if force:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"[INDEX] Deleted existing collection '{COLLECTION_NAME}'")
        except (ValueError, Exception):
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    existing = collection.count()
    if existing > 0 and not force:
        print(f"[INDEX] Collection already has {existing} documents. Use --force to rebuild.")
        return

    total = len(chunks)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = chunks[start:end]

        ids = [f"chunk_{start + i}" for i in range(len(batch))]
        documents = [c["content"] for c in batch]
        metadatas = [_flatten_metadata(c["metadata"]) for c in batch]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"  [{end}/{total}] indexed")

    print(f"\n[INDEX] Done. {collection.count()} documents in collection '{COLLECTION_NAME}'")
    print(f"[INDEX] Stored at {CHROMA_DIR}")


def get_collection():
    """Return existing ChromaDB collection for querying."""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    ef = DefaultEmbeddingFunction()
    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
    )


def _print_summary(chunks_path):
    """Print summary statistics from chunks JSON."""
    with open(chunks_path) as f:
        chunks = json.load(f)

    print(f"\nTotal documents: {len(chunks)}")

    type_counts = Counter(c["metadata"].get("content_type", "unknown") for c in chunks)
    print("\nBy content_type:")
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")

    version_counts = Counter(
        c["metadata"].get("ocpp_version", "other") for c in chunks
    )
    print("\nBy ocpp_version:")
    for v, count in sorted(version_counts.items(), key=lambda x: str(x[0])):
        print(f"  {v}: {count}")

    doc_counts = Counter(c["metadata"].get("doc_id", "unknown") for c in chunks)
    print("\nBy doc_id:")
    for d, count in sorted(doc_counts.items()):
        print(f"  {d}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Build ChromaDB index from OCPP chunks")
    parser.add_argument("--force", action="store_true", help="Rebuild index from scratch")
    parser.add_argument(
        "--chunks",
        type=str,
        default=None,
        help=f"Path to chunks JSON (default: {CHUNKS_DIR / '_all_chunks.json'})",
    )
    args = parser.parse_args()

    chunks_path = Path(args.chunks) if args.chunks else CHUNKS_DIR / "_all_chunks.json"

    build_index(chunks_path=chunks_path, force=args.force)

    if chunks_path.exists():
        _print_summary(chunks_path)


if __name__ == "__main__":
    main()
