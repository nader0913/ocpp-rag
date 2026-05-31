# OCPP RAG

RAG (Retrieval-Augmented Generation) knowledge base for EV charging protocols. Covers OCPP 1.6, OCPP 2.0.1, Plug & Charge, and related EV standards.

Built with [LlamaParse](https://docs.llamaindex.ai/en/stable/llama_cloud/llama_parse/) for document parsing, [ChromaDB](https://www.trychroma.com/) for vector storage, and exposed as an [MCP server](https://modelcontextprotocol.io/) for use with AI assistants.

## Document Coverage

| Document | Version | Status |
|----------|---------|--------|
| OCPP 2.0.1 Part 0 - Introduction | Edition 4 | Included |
| OCPP 2.0.1 Part 1 - Architecture & Topology | Edition 4 | Included |
| OCPP 2.0.1 Part 2 - Specification | Edition 4 | Included |
| OCPP 2.0.1 Part 2 - Appendices | v1.5 | Included |
| OCPP 2.0.1 Part 3 - JSON Schemas | Edition 4 | Included |
| OCPP 2.0.1 Part 4 - OCPP-J Specification | Edition 4 | Included |
| OCPP 2.0.1 Part 5 - Certification Profiles | Edition 4 | Included |
| OCPP 2.0.1 Part 6 - Test Cases | Edition 4 | Included |
| OCPP 2.0.1 Errata | 2026-04 | Included |
| OCPP 1.6 Specification | Edition 2 | Included |
| OCPP-J 1.6 Specification | Edition 2 | Included |
| ISO 15118 Plug & Charge with OCPP 1.6 (OCA Whitepaper) | v1.0 | Included |
| Appendices CSV Data (Components, Variables, Reason Codes, Security Events) | v1.5 | Included |

## Architecture

```
Source PDFs/ZIPs
       |
       v
  LlamaParse          extract_archives.py
  (parse.py)          (JSON schemas + CSVs)
       |                      |
       v                      v
   Markdown              Structured JSON
       |                      |
       +----------+-----------+
                  |
                  v
            chunk.py
          (smart chunking with metadata)
                  |
                  v
            index.py
          (ChromaDB vector index)
                  |
          +-------+-------+
          |               |
          v               v
     query.py        mcp_server.py
   (CLI + Claude)    (MCP tools)
```

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Set up API keys

```bash
cp .env.example .env
# Edit .env with your keys:
#   LLAMA_CLOUD_API_KEY=llx-...   (for parsing PDFs)
#   ANTHROPIC_API_KEY=sk-ant-...  (for query CLI)
```

### 3. Get source documents

Place OCPP 2.0.1 documents in `source_docs/OCPP-2.0.1_all_files/`. Download them from [openchargealliance.org](https://openchargealliance.org/download-ocpp/).

Download freely available additional documents:

```bash
uv run python scripts/download_docs.py
```

### 4. Extract archives

```bash
uv run python -m ocpp_rag.extract_archives
```

### 5. Parse all PDFs

```bash
# Parse all documents (requires LLAMA_CLOUD_API_KEY)
uv run python -m ocpp_rag.parse

# Or parse specific documents
uv run python -m ocpp_rag.parse --doc ocpp201_part2

# List document status
uv run python -m ocpp_rag.parse --list
```

### 6. Chunk and index

```bash
# Chunk all parsed documents
uv run python -m ocpp_rag.chunk

# Build vector index
uv run python -m ocpp_rag.index --force
```

### 7. Query

```bash
# Interactive mode
uv run python -m ocpp_rag.query

# Single question
uv run python -m ocpp_rag.query "How does cold boot work in OCPP 2.0.1?"

# Version-specific query
uv run python -m ocpp_rag.query --version 1.6 "How does authorization work?"
```

## MCP Server

The MCP server exposes the knowledge base as tools for AI assistants.

### Tools

| Tool | Description |
|------|-------------|
| `search_ocpp` | Semantic search across all documents with optional version/type filters |
| `get_use_case` | Get all details for a specific use case (e.g. "B01", "K08") |
| `list_use_cases` | List all use case IDs with filters |
| `get_message_schema` | Look up JSON schema for an OCPP message |
| `get_component_variable` | Look up device model components and variables |
| `list_documents` | List all indexed documents |
| `compare_versions` | Search a topic across OCPP 1.6 and 2.0.1 |

### Configure in Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ocpp-rag": {
      "command": "uv",
      "args": ["--directory", "/path/to/ocpp-rag", "run", "python", "-m", "ocpp_rag.mcp_server"]
    }
  }
}
```

### Configure in Claude Code

```bash
claude mcp add ocpp-rag -- uv --directory /path/to/ocpp-rag run python -m ocpp_rag.mcp_server
```

## Development

### Run tests

```bash
uv sync --extra dev
uv run pytest

# Skip integration tests
uv run pytest -m "not integration"
```

### Project structure

```
src/ocpp_rag/
  config.py              # Paths, document registry, constants
  parse.py               # LlamaParse PDF parsing pipeline
  extract_archives.py    # ZIP extraction (JSON schemas, CSVs)
  chunk.py               # Smart chunking with metadata
  index.py               # ChromaDB vector index builder
  mcp_server.py          # MCP server with 7 tools
  query.py               # Interactive query CLI
scripts/
  download_docs.py       # Download freely available documents
tests/
  conftest.py            # Shared fixtures
  test_config.py         # Config validation
  test_chunk.py          # Chunking logic tests
  test_extract_archives.py  # Archive extraction tests
  test_index.py          # Vector index tests
  test_mcp_server.py     # MCP server tool tests
  test_end_to_end.py     # Full pipeline integration tests
```

## License

MIT
