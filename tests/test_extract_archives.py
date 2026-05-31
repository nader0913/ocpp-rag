"""Tests for ocpp_rag.extract_archives module."""

import csv
import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ocpp_rag.extract_archives import (
    SCHEMAS_ZIP,
    APPENDICES_ZIP,
    _resolve_property_type,
    _extract_properties,
    _determine_direction,
    _read_csv_from_zip,
    _parse_components,
    _parse_variables,
    _parse_dm_components_vars,
    _parse_reason_codes,
    _parse_security_events,
    _parse_units_of_measure,
    extract_json_schemas,
    extract_csv_appendices,
)


class TestResolvePropertyType:
    """Test _resolve_property_type resolves JSON schema types correctly."""

    def test_simple_string(self):
        prop = {"type": "string"}
        result = _resolve_property_type(prop, {})
        assert result == "string"

    def test_integer(self):
        prop = {"type": "integer"}
        result = _resolve_property_type(prop, {})
        assert result == "integer"

    def test_string_with_format(self):
        prop = {"type": "string", "format": "date-time"}
        result = _resolve_property_type(prop, {})
        assert result == "string(date-time)"

    def test_enum_inline(self):
        prop = {"type": "string", "enum": ["Accepted", "Rejected"]}
        result = _resolve_property_type(prop, {})
        assert result == "enum(Accepted,Rejected)"

    def test_ref_to_definition(self):
        prop = {"$ref": "#/definitions/ChargingStationType"}
        definitions = {"ChargingStationType": {"type": "object"}}
        result = _resolve_property_type(prop, definitions)
        assert result == "ChargingStationType"

    def test_ref_to_enum_definition(self):
        prop = {"$ref": "#/definitions/StatusEnumType"}
        definitions = {"StatusEnumType": {"enum": ["Accepted", "Rejected", "Pending"]}}
        result = _resolve_property_type(prop, definitions)
        assert result == "enum(Accepted,Rejected,Pending)"

    def test_array_of_simple_type(self):
        prop = {"type": "array", "items": {"type": "string"}}
        result = _resolve_property_type(prop, {})
        assert result == "array<string>"

    def test_array_of_ref(self):
        prop = {"type": "array", "items": {"$ref": "#/definitions/IdTokenInfoType"}}
        definitions = {"IdTokenInfoType": {"type": "object"}}
        result = _resolve_property_type(prop, definitions)
        assert result == "array<IdTokenInfoType>"

    def test_unknown_type(self):
        prop = {}
        result = _resolve_property_type(prop, {})
        assert result == "unknown"


class TestExtractProperties:
    """Test _extract_properties extracts flat list from schema."""

    def test_basic_properties(self):
        schema = {
            "properties": {
                "status": {"type": "string", "description": "Status value"},
                "interval": {"type": "integer", "description": "Interval in seconds"},
            },
            "required": ["status"],
        }
        result = _extract_properties(schema)
        assert len(result) == 2

        status_prop = next(p for p in result if p["name"] == "status")
        assert status_prop["type"] == "string"
        assert status_prop["required"] is True
        assert status_prop["description"] == "Status value"

        interval_prop = next(p for p in result if p["name"] == "interval")
        assert interval_prop["required"] is False

    def test_ref_property_gets_description_from_definition(self):
        schema = {
            "properties": {
                "chargingStation": {"$ref": "#/definitions/ChargingStationType"},
            },
            "required": ["chargingStation"],
            "definitions": {
                "ChargingStationType": {
                    "type": "object",
                    "description": "Charging station info",
                },
            },
        }
        result = _extract_properties(schema)
        assert len(result) == 1
        assert result[0]["description"] == "Charging station info"

    def test_empty_properties(self):
        schema = {"properties": {}}
        result = _extract_properties(schema)
        assert result == []


class TestDetermineDirection:
    """Test _determine_direction from message name."""

    def test_request(self):
        assert _determine_direction("BootNotificationRequest") == "Request"

    def test_response(self):
        assert _determine_direction("BootNotificationResponse") == "Response"

    def test_unknown(self):
        assert _determine_direction("SomeOtherMessage") == "Unknown"


class TestReadCsvFromZip:
    """Test _read_csv_from_zip reads semicolon-delimited CSV."""

    def test_reads_csv_from_zip(self, tmp_path):
        csv_content = "Component;Description\nEVSE;Electric Vehicle Supply Equipment\nConnector;A connector\n"
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/components.csv", csv_content.encode("utf-8"))

        with zipfile.ZipFile(zip_path, "r") as zf:
            rows = _read_csv_from_zip(zf, "data/components.csv")

        assert len(rows) == 2
        assert rows[0]["Component"] == "EVSE"
        assert rows[0]["Description"] == "Electric Vehicle Supply Equipment"
        assert rows[1]["Component"] == "Connector"

    def test_handles_latin1_encoding(self, tmp_path):
        csv_content = "Name;Description\nTest;Stra\xdfe\n"
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test.csv", csv_content.encode("latin-1"))

        with zipfile.ZipFile(zip_path, "r") as zf:
            rows = _read_csv_from_zip(zf, "test.csv")

        assert len(rows) == 1
        assert "Stra" in rows[0]["Description"]

    def test_strips_whitespace(self, tmp_path):
        csv_content = " Name ; Description \n val1 ; val2 \n"
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test.csv", csv_content.encode("utf-8"))

        with zipfile.ZipFile(zip_path, "r") as zf:
            rows = _read_csv_from_zip(zf, "test.csv")

        assert rows[0]["Name"] == "val1"
        assert rows[0]["Description"] == "val2"


class TestParsers:
    """Test individual CSV parsers."""

    def test_parse_components(self):
        rows = [
            {"Component": "EVSE", "Description": "Electric Vehicle Supply Equipment"},
            {"Component": "Connector", "Description": "A connector"},
            {"Component": "", "Description": "Should be skipped"},
        ]
        result = _parse_components(rows)
        assert len(result) == 2
        assert result[0]["component"] == "EVSE"
        assert result[1]["component"] == "Connector"

    def test_parse_variables(self):
        rows = [
            {"Name": "Enabled", "DataType": "boolean", "Unit": "", "Description": "Whether enabled"},
            {"Name": "", "DataType": "string", "Unit": "", "Description": "Skip this"},
            {"Name": "Power", "DataType": "decimal", "Unit": "W", "Description": "Max power"},
        ]
        result = _parse_variables(rows)
        assert len(result) == 2
        assert result[0]["name"] == "Enabled"
        assert result[0]["data_type"] == "boolean"
        assert result[1]["name"] == "Power"
        assert result[1]["unit"] == "W"

    def test_parse_dm_components_vars(self):
        rows = [
            {
                "Specific Component": "EVSE",
                "Variable": "Enabled",
                "Instance": "",
                "Required?": "Yes",
                "DataType": "boolean",
                "Unit": "",
                "Description": "Is EVSE enabled",
            },
            {
                "Specific Component": "",
                "Variable": "",
                "Instance": "",
                "Required?": "",
                "DataType": "",
                "Unit": "",
                "Description": "Empty row",
            },
        ]
        result = _parse_dm_components_vars(rows)
        assert len(result) == 1
        assert result[0]["specific_component"] == "EVSE"
        assert result[0]["variable"] == "Enabled"
        assert result[0]["required"] == "Yes"

    def test_parse_reason_codes_forward_fills_group(self):
        rows = [
            {"Group": "Transaction", "Reason code": "EVDisconnected", "Description": "EV disconnected", "Typically used for": "End of charge"},
            {"Group": "", "Reason code": "PowerLoss", "Description": "Power lost", "Typically used for": "Abnormal end"},
            {"Group": "System", "Reason code": "Reboot", "Description": "System reboot", "Typically used for": "Maintenance"},
        ]
        result = _parse_reason_codes(rows)
        assert len(result) == 3
        assert result[0]["group"] == "Transaction"
        assert result[1]["group"] == "Transaction"  # forward-filled
        assert result[2]["group"] == "System"

    def test_parse_reason_codes_skips_empty_code(self):
        rows = [
            {"Group": "Transaction", "Reason code": "", "Description": "No code", "Typically used for": ""},
        ]
        result = _parse_reason_codes(rows)
        assert len(result) == 0

    def test_parse_security_events(self):
        rows = [
            {"Security Event": "FirmwareUpdated", "Description": "Firmware was updated", "Critical": "No"},
            {"Security Event": "", "Description": "Empty", "Critical": ""},
        ]
        result = _parse_security_events(rows)
        assert len(result) == 1
        assert result[0]["security_event"] == "FirmwareUpdated"
        assert result[0]["critical"] == "No"

    def test_parse_units_of_measure(self):
        rows = [
            {"Value": "W", "Description": "Watt"},
            {"Value": "Wh", "Description": "Watt-hour"},
            {"Value": "", "Description": "Empty"},
        ]
        result = _parse_units_of_measure(rows)
        assert len(result) == 2
        assert result[0]["unit"] == "W"
        assert result[1]["unit"] == "Wh"


@pytest.mark.skipif(
    not SCHEMAS_ZIP.exists(),
    reason=f"Schemas ZIP not found at {SCHEMAS_ZIP}",
)
class TestExtractJsonSchemasReal:
    """Integration tests that require the actual OCPP schemas ZIP file."""

    def test_extract_returns_schemas(self):
        schemas = extract_json_schemas()
        assert len(schemas) > 0

    def test_schema_structure(self):
        schemas = extract_json_schemas()
        for schema in schemas:
            assert "message_name" in schema
            assert "direction" in schema
            assert "schema" in schema
            assert "properties" in schema
            assert schema["direction"] in ("Request", "Response", "Unknown")

    def test_has_common_messages(self):
        schemas = extract_json_schemas()
        message_names = {s["message_name"] for s in schemas}
        assert "BootNotificationRequest" in message_names
        assert "BootNotificationResponse" in message_names
        assert "AuthorizeRequest" in message_names
        assert "HeartbeatRequest" in message_names

    def test_request_response_pairs(self):
        schemas = extract_json_schemas()
        requests = {s["message_name"] for s in schemas if s["direction"] == "Request"}
        responses = {s["message_name"] for s in schemas if s["direction"] == "Response"}
        # Most requests should have a corresponding response
        for req in requests:
            base = req.removesuffix("Request")
            resp = f"{base}Response"
            assert resp in responses, f"No response found for {req}"


@pytest.mark.skipif(
    not APPENDICES_ZIP.exists(),
    reason=f"Appendices ZIP not found at {APPENDICES_ZIP}",
)
class TestExtractCsvAppendicesReal:
    """Integration tests that require the actual appendices ZIP file."""

    def test_extract_returns_data(self):
        data = extract_csv_appendices()
        assert len(data) > 0

    def test_all_expected_categories(self):
        data = extract_csv_appendices()
        expected = {"components", "variables", "reason_codes", "security_events", "units_of_measure"}
        for key in expected:
            assert key in data, f"Missing category: {key}"
            assert len(data[key]) > 0, f"Empty category: {key}"

    def test_components_have_required_fields(self):
        data = extract_csv_appendices()
        for comp in data["components"]:
            assert "component" in comp
            assert len(comp["component"]) > 0

    def test_variables_have_required_fields(self):
        data = extract_csv_appendices()
        for var in data["variables"]:
            assert "name" in var
            assert len(var["name"]) > 0


class TestExtractJsonSchemasMocked:
    """Test extract_json_schemas with mocked ZIP file."""

    def test_extract_from_zip(self, tmp_path):
        # Create a test ZIP with JSON schemas
        schema_content = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Status value"},
            },
            "required": ["status"],
        }

        zip_path = tmp_path / "schemas.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("schemas/TestRequest.json", json.dumps(schema_content))
            zf.writestr("schemas/TestResponse.json", json.dumps(schema_content))

        schemas_dir = tmp_path / "output_schemas"
        individual_dir = schemas_dir / "individual"

        with patch("ocpp_rag.extract_archives.SCHEMAS_ZIP", zip_path), \
             patch("ocpp_rag.extract_archives.SCHEMAS_DIR", schemas_dir), \
             patch("ocpp_rag.extract_archives.INDIVIDUAL_SCHEMAS_DIR", individual_dir):
            schemas = extract_json_schemas()

        assert len(schemas) == 2
        names = {s["message_name"] for s in schemas}
        assert "TestRequest" in names
        assert "TestResponse" in names

        # Verify directions
        for s in schemas:
            if s["message_name"] == "TestRequest":
                assert s["direction"] == "Request"
            else:
                assert s["direction"] == "Response"

        # Verify properties extracted
        for s in schemas:
            assert len(s["properties"]) == 1
            assert s["properties"][0]["name"] == "status"

    def test_individual_files_written(self, tmp_path):
        schema_content = {"type": "object", "properties": {}}
        zip_path = tmp_path / "schemas.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("AuthorizeRequest.json", json.dumps(schema_content))

        schemas_dir = tmp_path / "output_schemas"
        individual_dir = schemas_dir / "individual"

        with patch("ocpp_rag.extract_archives.SCHEMAS_ZIP", zip_path), \
             patch("ocpp_rag.extract_archives.SCHEMAS_DIR", schemas_dir), \
             patch("ocpp_rag.extract_archives.INDIVIDUAL_SCHEMAS_DIR", individual_dir):
            extract_json_schemas()

        assert (individual_dir / "AuthorizeRequest.json").exists()
        assert (schemas_dir / "all_schemas.json").exists()


class TestExtractCsvAppendicesMocked:
    """Test extract_csv_appendices with mocked ZIP file."""

    def test_extract_from_zip(self, tmp_path):
        zip_path = tmp_path / "appendices.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "data/components.csv",
                "Component;Description\nEVSE;Electric Vehicle Supply Equipment\n".encode("utf-8"),
            )
            zf.writestr(
                "data/variables.csv",
                "Name;DataType;Unit;Description\nEnabled;boolean;;Whether enabled\n".encode("utf-8"),
            )
            zf.writestr(
                "data/reason_codes.csv",
                "Group;Reason code;Description;Typically used for\nTransaction;EVDisconnected;EV disconnected;End\n".encode("utf-8"),
            )
            zf.writestr(
                "data/security_events.csv",
                "Security Event;Description;Critical\nFirmwareUpdated;Updated;No\n".encode("utf-8"),
            )
            zf.writestr(
                "data/units_of_measure.csv",
                "Value;Description\nW;Watt\n".encode("utf-8"),
            )

        appendices_dir = tmp_path / "output_appendices"

        with patch("ocpp_rag.extract_archives.APPENDICES_ZIP", zip_path), \
             patch("ocpp_rag.extract_archives.APPENDICES_DIR", appendices_dir):
            data = extract_csv_appendices()

        assert "components" in data
        assert len(data["components"]) == 1
        assert data["components"][0]["component"] == "EVSE"

        assert "variables" in data
        assert len(data["variables"]) == 1

        assert "reason_codes" in data
        assert len(data["reason_codes"]) == 1

        assert "security_events" in data
        assert "units_of_measure" in data

    def test_consolidated_file_written(self, tmp_path):
        zip_path = tmp_path / "appendices.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "components.csv",
                "Component;Description\nTest;A test\n".encode("utf-8"),
            )

        appendices_dir = tmp_path / "output_appendices"

        with patch("ocpp_rag.extract_archives.APPENDICES_ZIP", zip_path), \
             patch("ocpp_rag.extract_archives.APPENDICES_DIR", appendices_dir):
            extract_csv_appendices()

        consolidated = appendices_dir / "all_appendices.json"
        assert consolidated.exists()
        data = json.loads(consolidated.read_text())
        assert "components" in data
