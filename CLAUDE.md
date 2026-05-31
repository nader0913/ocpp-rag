# OCPP RAG

RAG knowledge base for EV charging protocols (OCPP 1.6, 2.0.1, Plug & Charge).

## Key Commands

```bash
uv sync                                    # Install dependencies
uv run python scripts/download_docs.py     # Download OCPP 1.6 + PnC docs
uv run python -m ocpp_rag.extract_archives # Extract JSON schemas + CSVs from zips
uv run python -m ocpp_rag.parse            # Parse all PDFs with LlamaParse
uv run python -m ocpp_rag.chunk            # Chunk parsed documents
uv run python -m ocpp_rag.index --force    # Build ChromaDB vector index
uv run python -m ocpp_rag.query            # Interactive query CLI
uv run pytest                              # Run tests
uv run pytest -m "not integration"         # Skip integration tests
```

## Architecture

Source PDFs → LlamaParse (parse.py) → Markdown → chunk.py → ChromaDB (index.py) → MCP server / Query CLI

## Key Files

- `src/ocpp_rag/config.py` — All paths, document registry (ALL_DOCS), functional blocks
- `src/ocpp_rag/parse.py` — LlamaParse pipeline, handles all document types
- `src/ocpp_rag/chunk.py` — Smart chunking with provenance metadata
- `src/ocpp_rag/index.py` — ChromaDB index builder, get_collection() shared function
- `src/ocpp_rag/mcp_server.py` — FastMCP server with 7 tools
- `src/ocpp_rag/query.py` — Interactive CLI with Claude

## Document Registry

Documents are registered in `config.py` ALL_DOCS dict. Each has a doc_id, title, file path relative to source_docs/, and ocpp_version.

## Chunking Metadata

Every chunk has: doc_id, doc_title, ocpp_version, content_type, heading, heading_path. Use case chunks also have: functional_block, use_case_id, use_case_name.

## API Keys

- LLAMA_CLOUD_API_KEY — Required for parsing PDFs
- ANTHROPIC_API_KEY — Required for query CLI (not needed for MCP server)
