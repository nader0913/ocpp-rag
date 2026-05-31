# OCPP RAG

MCP server providing OCPP 1.6, 2.0.1, and EV charging protocol knowledge to AI assistants.

## Run MCP server
```bash
uv run python -m ocpp_rag.mcp_server
```

## Run tests
```bash
uv sync --extra dev
uv run pytest
```

## Key files
- `src/ocpp_rag/mcp_server.py` — MCP server with 7 tools, auto-builds index on first run
- `src/ocpp_rag/data/chunks.json` — Pre-built knowledge base (3,800+ chunks from 13 documents)
- `src/ocpp_rag/config.py` — Paths and constants
- `src/ocpp_rag/index.py` — ChromaDB index builder

## Index location
ChromaDB index is cached at `~/.cache/ocpp-rag/chroma_db/` (override with `OCPP_RAG_CACHE_DIR` env var).
