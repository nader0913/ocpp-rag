# OCPP RAG

MCP server that gives AI assistants deep knowledge of EV charging protocols. Add it to Claude and ask anything about OCPP 1.6, OCPP 2.0.1, Plug & Charge, smart charging, and related standards.

3,500+ indexed chunks from 18 official documents, 119 structured use cases, 128 JSON schemas, and 146 figures.

## Quick Start

### Claude Code

```bash
claude mcp add ocpp-rag -- uvx --from git+https://github.com/nader0913/ocpp-rag python -m ocpp_rag.mcp_server
```

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ocpp-rag": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nader0913/ocpp-rag", "python", "-m", "ocpp_rag.mcp_server"]
    }
  }
}
```

### Local Development

```bash
git clone https://github.com/nader0913/ocpp-rag.git
cd ocpp-rag
uv sync
uv run python -m ocpp_rag.mcp_server
```

The ChromaDB index builds automatically on first run (~30 seconds).

## Tools

| Tool | Description |
|------|-------------|
| `search_ocpp` | Semantic search across all 18 documents. Filter by version (`1.6` / `2.0.1`) or content type (`use_case`, `requirements`, `json_schema`, `component_variable`). |
| `get_use_case` | Retrieve full structured details for any use case (e.g. `B01`, `E02`, `K08`) including description, actors, scenario, requirements, and figures. |
| `list_use_cases` | List all use cases, filterable by OCPP version and functional block. |
| `get_message_schema` | Look up the JSON schema for any OCPP 2.0.1 message (e.g. `BootNotificationRequest`, `TransactionEventResponse`). |
| `get_component_variable` | Query device model components and variables from the OCPP 2.0.1 appendices. |
| `list_documents` | List all indexed documents with chunk counts. |
| `compare_versions` | Search a topic across OCPP 1.6 and 2.0.1 side by side. |

## What's Inside

### OCPP 2.0.1 (Edition 4)

- **Part 0** - Introduction
- **Part 1** - Architecture & Topology
- **Part 2** - Specification (491 pages, 119 use cases across 16 functional blocks A-P)
- **Part 2** - Appendices (device model: 82 components, 214 variables)
- **Part 3** - JSON Schemas (128 message schemas)
- **Part 4** - OCPP-J Specification (WebSocket/JSON transport)
- **Part 5** - Certification Profiles
- **Part 6** - Test Cases
- **Errata** (2026-04)

### OCPP 1.6

- OCPP 1.6 Specification (24 operations)
- OCPP-J 1.6 Specification

### Whitepapers & Guides

- Using ISO 15118 Plug & Charge with OCPP 1.6
- OCPP & California Pricing Requirements v3.1
- OCPP 1.6 Security Whitepaper (Edition 4)
- OCPP Security Operations Guide v1.0
- What is New in OCPP 2.0.1
- OCPP 2.Lite - OCPP for Resource-Constrained Devices v2

### Figures

146 cleanly extracted diagrams from the OCPP 2.0.1 specification: sequence diagrams, state machines, topology diagrams, PKI hierarchies, and more.

## Data Structure

```
src/ocpp_rag/data/
  ocpp201/
    use_cases/       119 structured JSON files (A01.json - P02.json)
    schemas/         128 JSON schema files
    blocks/          16 functional block introductions
    appendices/      Device model components & variables
    part0-6, errata  Chunked specification text
  ocpp16/
    spec.json        OCPP 1.6 specification
    j.json           OCPP-J 1.6
  other/
    6 whitepaper JSON files
  figures/
    146 PNG files + manifest
```

Each use case is stored as structured JSON with proper fields:

```json
{
  "name": "Cold Boot Charging Station",
  "id": "B01",
  "functional_block": "Provisioning",
  "objective": "...",
  "description": "...",
  "actors": ["Charging Station", "CSMS"],
  "scenario": ["1. The Charging Station is powered up.", "..."],
  "prerequisites": "...",
  "postconditions": "...",
  "requirements": [
    {"id": "B01.FR.01", "precondition": "...", "definition": "..."}
  ],
  "figures": ["fig10.png"]
}
```

## Example Queries

- *"How does cold boot work in OCPP 2.0.1? Show me the requirements."*
- *"What's the JSON schema for TransactionEventRequest?"*
- *"Compare authorization between OCPP 1.6 and 2.0.1"*
- *"List all Smart Charging use cases"*
- *"What device model variables are available for the EVSE component?"*
- *"How does Plug & Charge work with ISO 15118?"*
- *"What are the California pricing requirements for OCPP?"*
- *"What security profiles exist in OCPP 1.6?"*

## Running Tests

```bash
uv sync --extra dev
uv run pytest
```

## Configuration

The ChromaDB index is cached at `~/.cache/ocpp-rag/chroma_db/`. Override with:

```bash
export OCPP_RAG_CACHE_DIR=/your/path
```

## License

This project is licensed under the [Polyform Noncommercial License 1.0.0](LICENSE).

**Free** for personal use, research, education, non-profits, and government institutions.

**Commercial use** requires a separate license. Contact [ouerdiane.nader@gmail.com](mailto:ouerdiane.nader@gmail.com) for commercial licensing.
