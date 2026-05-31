# OCPP RAG

MCP server that gives AI assistants deep knowledge of EV charging protocols. Connect it to Claude and ask anything about OCPP 1.6, OCPP 2.0.1, Plug & Charge, and related standards.

**3,800+ indexed chunks** from 13 official documents — use cases, requirements, message schemas, device model variables, test cases, and more.

## Setup

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

### Local install

```bash
git clone https://github.com/nader0913/ocpp-rag.git
cd ocpp-rag
uv sync
```

Then add to Claude Code:
```bash
claude mcp add ocpp-rag -- uv --directory /path/to/ocpp-rag run python -m ocpp_rag.mcp_server
```

The index builds automatically on first run (~30 seconds).

## Tools

| Tool | What it does |
|------|-------------|
| `search_ocpp` | Semantic search across all documents. Filter by version ("1.6" / "2.0.1") or content type. |
| `get_use_case` | Get full details for a use case — description, sequence diagram, requirements (e.g. "B01", "K08"). |
| `list_use_cases` | List all use case IDs, filterable by version and functional block. |
| `get_message_schema` | Look up the JSON schema for any OCPP 2.0.1 message (e.g. "BootNotificationRequest"). |
| `get_component_variable` | Look up device model components and variables from the appendices. |
| `list_documents` | List all indexed documents with chunk counts. |
| `compare_versions` | Search a topic across OCPP 1.6 and 2.0.1 side by side. |

## Document Coverage

### OCPP 2.0.1 (Edition 4)
- Part 0 — Introduction
- Part 1 — Architecture & Topology
- Part 2 — Specification (491 pages, 119 use cases, 16 functional blocks A-P)
- Part 2 — Appendices (components, variables, device model)
- Part 3 — JSON Schemas (128 message schemas, 64 request/response pairs)
- Part 4 — OCPP-J Specification (WebSocket/JSON transport)
- Part 5 — Certification Profiles
- Part 6 — Test Cases (916 pages)
- Errata (2026-04)
- Appendices CSV (82 components, 214 variables, 51 reason codes, 21 security events, 34 units)

### OCPP 1.6
- OCPP 1.6 Specification
- OCPP-J 1.6 Specification

### Other
- Using ISO 15118 Plug & Charge with OCPP 1.6 (OCA Whitepaper)

## Example Queries

Once connected, ask Claude things like:

- "How does cold boot work in OCPP 2.0.1? Show me the requirements."
- "What's the JSON schema for TransactionEventRequest?"
- "Compare authorization between OCPP 1.6 and 2.0.1"
- "List all Smart Charging use cases"
- "What device model variables are available for the EVSE component?"
- "How does Plug & Charge work with ISO 15118?"

## License

MIT
