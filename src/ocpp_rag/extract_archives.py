"""Extract and process OCPP 2.0.1 ZIP archives (JSON schemas and CSV appendices).

Extracts structured data from:
- OCPP-2.0.1_part3_JSON_schemas.zip: ~60+ JSON schema files for OCPP messages
- Appendices_CSV_v1.5.zip: CSV files for components, variables, reason codes, etc.

Usage:
    python -m ocpp_rag.extract_archives
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from ocpp_rag.config import APPENDICES_DIR, SCHEMAS_DIR, SOURCE_DOCS_DIR

SCHEMAS_ZIP = SOURCE_DOCS_DIR / "OCPP-2.0.1_all_files" / "OCPP-2.0.1_part3_JSON_schemas.zip"
APPENDICES_ZIP = SOURCE_DOCS_DIR / "OCPP-2.0.1_all_files" / "Appendices_CSV_v1.5.zip"

INDIVIDUAL_SCHEMAS_DIR = SCHEMAS_DIR / "individual"


# ---------------------------------------------------------------------------
# JSON Schema extraction
# ---------------------------------------------------------------------------

def _resolve_property_type(prop: dict[str, Any], definitions: dict[str, Any]) -> str:
    """Resolve the effective type of a JSON schema property.

    Handles direct types, $ref to definitions, and arrays.
    """
    if "$ref" in prop:
        ref_name = prop["$ref"].rsplit("/", 1)[-1]
        defn = definitions.get(ref_name, {})
        # If the referenced definition is an enum, report it as such
        if "enum" in defn:
            return f"enum({','.join(defn['enum'])})"
        return ref_name

    prop_type = prop.get("type", "unknown")

    if prop_type == "array":
        items = prop.get("items", {})
        inner = _resolve_property_type(items, definitions)
        return f"array<{inner}>"

    if "enum" in prop:
        return f"enum({','.join(str(v) for v in prop['enum'])})"

    fmt = prop.get("format")
    if fmt:
        return f"{prop_type}({fmt})"

    return prop_type


def _extract_properties(
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract a flat list of property metadata from a schema's top-level properties."""
    definitions = schema.get("definitions", {})
    required_fields = set(schema.get("required", []))
    properties = schema.get("properties", {})

    result: list[dict[str, Any]] = []
    for name, prop in properties.items():
        description = prop.get("description", "")
        if not description and "$ref" in prop:
            ref_name = prop["$ref"].rsplit("/", 1)[-1]
            defn = definitions.get(ref_name, {})
            description = defn.get("description", "")
        # Clean up description whitespace
        description = " ".join(description.split())

        result.append(
            {
                "name": name,
                "type": _resolve_property_type(prop, definitions),
                "description": description,
                "required": name in required_fields,
            }
        )
    return result


def _determine_direction(message_name: str) -> str:
    """Return 'Request' or 'Response' based on the message name suffix."""
    if message_name.endswith("Request"):
        return "Request"
    if message_name.endswith("Response"):
        return "Response"
    return "Unknown"


def extract_json_schemas() -> list[dict[str, Any]]:
    """Extract all JSON schemas from the OCPP schemas ZIP.

    Returns a list of schema records and writes:
      - output/schemas/all_schemas.json  (consolidated)
      - output/schemas/individual/<MessageName>.json  (one per schema)
    """
    SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)
    INDIVIDUAL_SCHEMAS_DIR.mkdir(parents=True, exist_ok=True)

    all_schemas: list[dict[str, Any]] = []

    with zipfile.ZipFile(SCHEMAS_ZIP, "r") as zf:
        json_entries = sorted(
            name
            for name in zf.namelist()
            if name.endswith(".json")
        )

        for entry in json_entries:
            raw = zf.read(entry)
            schema = json.loads(raw)

            filename = Path(entry).name  # e.g. "AuthorizeRequest.json"
            message_name = filename.removesuffix(".json")

            record = {
                "message_name": message_name,
                "direction": _determine_direction(message_name),
                "schema": schema,
                "properties": _extract_properties(schema),
            }
            all_schemas.append(record)

            # Save individual schema file
            individual_path = INDIVIDUAL_SCHEMAS_DIR / filename
            individual_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    # Save consolidated output
    consolidated_path = SCHEMAS_DIR / "all_schemas.json"
    consolidated_path.write_text(json.dumps(all_schemas, indent=2), encoding="utf-8")

    return all_schemas


# ---------------------------------------------------------------------------
# CSV Appendices extraction
# ---------------------------------------------------------------------------

def _read_csv_from_zip(
    zf: zipfile.ZipFile,
    entry_name: str,
) -> list[dict[str, str]]:
    """Read a semicolon-delimited CSV from inside a ZipFile.

    Tries UTF-8 first, falls back to latin-1 for encoding robustness.
    Returns a list of dicts with stripped keys and values.
    """
    raw = zf.read(entry_name)

    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    rows: list[dict[str, str]] = []
    for row in reader:
        cleaned = {k.strip(): v.strip() for k, v in row.items() if k is not None}
        rows.append(cleaned)
    return rows


def _parse_components(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Parse components.csv rows into a clean structure."""
    return [
        {
            "component": row.get("Component", ""),
            "description": row.get("Description", ""),
        }
        for row in rows
        if row.get("Component", "").strip()
    ]


def _parse_variables(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Parse variables.csv rows into a clean structure."""
    return [
        {
            "name": row.get("Name", ""),
            "data_type": row.get("DataType", ""),
            "unit": row.get("Unit", ""),
            "description": row.get("Description", ""),
        }
        for row in rows
        if row.get("Name", "").strip()
    ]


def _parse_dm_components_vars(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Parse dm_components_vars.csv (device model component-variable mapping)."""
    return [
        {
            "specific_component": row.get("Specific Component", ""),
            "variable": row.get("Variable", ""),
            "instance": row.get("Instance", ""),
            "required": row.get("Required?", ""),
            "data_type": row.get("DataType", ""),
            "unit": row.get("Unit", ""),
            "description": row.get("Description", ""),
        }
        for row in rows
        if row.get("Variable", "").strip()
    ]


def _parse_reason_codes(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Parse reason_codes.csv rows.

    The CSV uses a 'Group' column that may be empty for rows that belong to
    the most recently seen group, so we forward-fill it.
    """
    result: list[dict[str, str]] = []
    current_group = ""
    for row in rows:
        group = row.get("Group", "").strip()
        if group:
            current_group = group
        code = row.get("Reason code", "").strip()
        if not code:
            continue
        result.append(
            {
                "group": current_group,
                "reason_code": code,
                "description": row.get("Description", ""),
                "typically_used_for": row.get("Typically used for", ""),
            }
        )
    return result


def _parse_security_events(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Parse security_events.csv rows."""
    return [
        {
            "security_event": row.get("Security Event", ""),
            "description": row.get("Description", ""),
            "critical": row.get("Critical", ""),
        }
        for row in rows
        if row.get("Security Event", "").strip()
    ]


def _parse_units_of_measure(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Parse units_of_measure.csv rows."""
    return [
        {
            "unit": row.get("Value", ""),
            "description": row.get("Description", ""),
        }
        for row in rows
        if row.get("Value", "").strip()
    ]


# Mapping from CSV filename (without path prefix) to its parser function.
_CSV_PARSERS: dict[str, tuple[str, Any]] = {
    "components.csv": ("components", _parse_components),
    "variables.csv": ("variables", _parse_variables),
    "dm_components_vars.csv": ("dm_components_vars", _parse_dm_components_vars),
    "reason_codes.csv": ("reason_codes", _parse_reason_codes),
    "security_events.csv": ("security_events", _parse_security_events),
    "units_of_measure.csv": ("units_of_measure", _parse_units_of_measure),
}


def extract_csv_appendices() -> dict[str, list[dict[str, str]]]:
    """Extract all CSV appendices from the appendices ZIP.

    Returns a dict keyed by appendix name and writes:
      - output/appendices/all_appendices.json  (consolidated)
    """
    APPENDICES_DIR.mkdir(parents=True, exist_ok=True)

    all_appendices: dict[str, list[dict[str, str]]] = {}

    with zipfile.ZipFile(APPENDICES_ZIP, "r") as zf:
        for entry in sorted(zf.namelist()):
            if not entry.endswith(".csv"):
                continue
            basename = Path(entry).name
            if basename not in _CSV_PARSERS:
                print(f"  [skip] No parser for {basename}, storing raw rows")
                rows = _read_csv_from_zip(zf, entry)
                all_appendices[basename.removesuffix(".csv")] = rows
                continue

            key, parser = _CSV_PARSERS[basename]
            rows = _read_csv_from_zip(zf, entry)
            parsed = parser(rows)
            all_appendices[key] = parsed

    # Save consolidated output
    consolidated_path = APPENDICES_DIR / "all_appendices.json"
    consolidated_path.write_text(json.dumps(all_appendices, indent=2), encoding="utf-8")

    return all_appendices


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Run both extractions and print summary statistics."""
    print("=" * 60)
    print("OCPP 2.0.1 Archive Extraction")
    print("=" * 60)

    # --- JSON Schemas ---
    print("\n--- JSON Schemas ---")
    print(f"Source: {SCHEMAS_ZIP}")
    schemas = extract_json_schemas()
    requests = [s for s in schemas if s["direction"] == "Request"]
    responses = [s for s in schemas if s["direction"] == "Response"]
    print(f"  Total schemas extracted: {len(schemas)}")
    print(f"  Request schemas:         {len(requests)}")
    print(f"  Response schemas:        {len(responses)}")

    # Count total properties across all schemas
    total_props = sum(len(s["properties"]) for s in schemas)
    print(f"  Total properties:        {total_props}")

    # List all unique message names (base name without Request/Response)
    base_names = sorted(
        {
            s["message_name"].removesuffix("Request").removesuffix("Response")
            for s in schemas
        }
    )
    print(f"  Unique message types:    {len(base_names)}")
    print(f"  Output: {SCHEMAS_DIR / 'all_schemas.json'}")
    print(f"  Individual schemas: {INDIVIDUAL_SCHEMAS_DIR}/")

    # --- CSV Appendices ---
    print("\n--- CSV Appendices ---")
    print(f"Source: {APPENDICES_ZIP}")
    appendices = extract_csv_appendices()
    for key, records in appendices.items():
        print(f"  {key}: {len(records)} records")
    print(f"  Output: {APPENDICES_DIR / 'all_appendices.json'}")

    print("\n" + "=" * 60)
    print("Extraction complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
