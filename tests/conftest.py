import pytest
import json
from pathlib import Path


@pytest.fixture
def sample_chunk():
    return {
        "content": "## A01 - Update Charging Station Password\n\nThe Charging Station SHALL...",
        "metadata": {
            "doc_id": "ocpp201_part2",
            "doc_title": "OCPP 2.0.1 Part 2 - Specification",
            "ocpp_version": "2.0.1",
            "content_type": "use_case",
            "heading": "A01 - Update Charging Station Password for HTTP Basic Authentication",
            "heading_path": "A. Security > A01 - Update Charging Station Password",
            "functional_block": "Security",
            "use_case_id": "A01",
        },
    }


@pytest.fixture
def sample_chunks():
    """A realistic set of chunks for testing."""
    return [
        {
            "content": "The Charging Station SHALL send BootNotificationRequest to the CSMS.",
            "metadata": {
                "doc_id": "ocpp201_part2",
                "doc_title": "OCPP 2.0.1 Part 2",
                "ocpp_version": "2.0.1",
                "content_type": "use_case",
                "heading": "B01 - Cold Boot Charging Station",
                "heading_path": "B. Provisioning > B01",
                "functional_block": "Provisioning",
                "use_case_id": "B01",
                "use_case_name": "Cold Boot Charging Station",
            },
        },
        {
            "content": "| ID | Precondition | Requirement |\n|---|---|---|\n| B01.FR.01 | After start-up | Send BootNotificationRequest |",
            "metadata": {
                "doc_id": "ocpp201_part2",
                "doc_title": "OCPP 2.0.1 Part 2",
                "ocpp_version": "2.0.1",
                "content_type": "requirements",
                "heading": "B01 - Cold Boot Charging Station - Requirements",
                "heading_path": "B. Provisioning > B01 > Requirements",
                "functional_block": "Provisioning",
                "use_case_id": "B01",
            },
        },
        {
            "content": "## BootNotificationRequest\n**Type**: OCPP 2.0.1 Message Schema",
            "metadata": {
                "doc_id": "ocpp201_json_schemas",
                "doc_title": "OCPP 2.0.1 JSON Schemas",
                "ocpp_version": "2.0.1",
                "content_type": "json_schema",
                "heading": "BootNotificationRequest",
                "message_name": "BootNotificationRequest",
            },
        },
        {
            "content": "Remote Procedure Call over WebSocket using JSON.",
            "metadata": {
                "doc_id": "ocpp16_j",
                "doc_title": "OCPP-J 1.6 Specification",
                "ocpp_version": "1.6",
                "content_type": "general",
                "heading": "Introduction",
            },
        },
    ]


@pytest.fixture
def output_dir(tmp_path):
    """Create a temporary output directory structure."""
    (tmp_path / "parsed").mkdir()
    (tmp_path / "chunks").mkdir()
    (tmp_path / "schemas").mkdir()
    (tmp_path / "appendices").mkdir()
    return tmp_path


@pytest.fixture
def sample_markdown_201():
    """Sample markdown mimicking OCPP 2.0.1 Part 2 structure."""
    return """\
[PAGE 42]

# A. Security

This functional block contains use cases related to the security of the system.
Security is a fundamental aspect of OCPP 2.0.1 and covers authentication,
authorization, and secure communication between Charging Stations and the CSMS.
All security use cases are prefixed with the letter A.

## A01 - Update Charging Station Password for HTTP Basic Authentication

| No. | Type | Description | Actors |
|---|---|---|---|
| 1 | Name | Update Charging Station Password for HTTP Basic Authentication | Charging Station, CSMS |
| 2 | ID | A01 | |
| 3 | Precondition | HTTP Basic Authentication is configured | |
| 4 | Description | The CSMS sends a new password to the Charging Station | |

The Charging Station SHALL accept the SetVariablesRequest message from the CSMS with BasicAuthPassword. See also B02 for provisioning details.

[PAGE 43]

## A01 - Update Charging Station Password for HTTP Basic Authentication - Requirements

| ID | Precondition | Requirement |
|---|---|---|
| A01.FR.01 | When a SetVariablesRequest is received with BasicAuthPassword | The Charging Station SHALL update the stored HTTP Basic Authentication password |
| A01.FR.02 | After password update | The Charging Station SHALL use the new password for subsequent connections |
| A01.FR.03 | If the new password does not meet security policy | The Charging Station SHALL reject the password change with a SetVariablesResponse |

## A02 - Certificate-Based Authentication

| No. | Type | Description |
|---|---|---|
| 1 | Name | Certificate-Based Authentication |
| 2 | ID | A02 |

The Charging Station uses X.509 certificates to authenticate. The Charging Station SHALL send a BootNotificationRequest after establishing a TLS session.

## Figure 1 - A01 Sequence Diagram

This is a sequence diagram showing the A01 flow.

# B. Provisioning

This functional block handles the provisioning of Charging Stations.
Provisioning covers boot processes, configuration management, and variable handling.
All provisioning use cases are prefixed with the letter B and are essential for
initial setup and ongoing management of Charging Stations connected to a CSMS.

## B01 - Cold Boot Charging Station

| No. | Type | Description |
|---|---|---|
| 1 | Name | Cold Boot Charging Station |
| 2 | ID | B01 |

After start-up, the Charging Station SHALL send a BootNotificationRequest to inform the CSMS of its availability. The CSMS responds with a BootNotificationResponse.

## B05 - Set Variables

| No. | Type | Description |
|---|---|---|
| 1 | Name | Set Variables |
| 2 | ID | B05 |

The CSMS can set configuration variables using SetVariablesRequest.

# K. SmartCharging

## K12 - Set Charging Profile

| No. | Type | Description |
|---|---|---|
| 1 | Name | Set Charging Profile |
| 2 | ID | K12 |

The CSMS can set a charging profile using SetChargingProfileRequest.
This is related to E02 transactions and uses K08 for composite schedules.
The Charging Station SHALL accept SetChargingProfileRequest and apply
the charging profile to the specified EVSE. If no EVSE is specified,
the profile applies to the entire Charging Station.
"""


@pytest.fixture
def sample_schemas_json(tmp_path):
    """Create a sample schemas JSON file."""
    schemas = [
        {
            "message_name": "BootNotificationRequest",
            "direction": "Request",
            "schema": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "enum": ["PowerUp", "ApplicationReset"]},
                    "chargingStation": {"$ref": "#/definitions/ChargingStationType"},
                },
                "required": ["reason", "chargingStation"],
                "definitions": {
                    "ChargingStationType": {
                        "type": "object",
                        "description": "The physical system where an EV can be charged.",
                        "properties": {
                            "model": {"type": "string"},
                            "vendorName": {"type": "string"},
                        },
                    }
                },
            },
            "properties": [
                {"name": "reason", "type": "enum(PowerUp,ApplicationReset)", "description": "The reason for boot", "required": True},
                {"name": "chargingStation", "type": "ChargingStationType", "description": "The physical system where an EV can be charged.", "required": True},
            ],
        },
        {
            "message_name": "BootNotificationResponse",
            "direction": "Response",
            "schema": {
                "type": "object",
                "properties": {
                    "currentTime": {"type": "string", "format": "date-time"},
                    "interval": {"type": "integer"},
                    "status": {"type": "string", "enum": ["Accepted", "Pending", "Rejected"]},
                },
                "required": ["currentTime", "interval", "status"],
            },
            "properties": [
                {"name": "currentTime", "type": "string(date-time)", "description": "Current time of CSMS", "required": True},
                {"name": "interval", "type": "integer", "description": "Heartbeat interval in seconds", "required": True},
                {"name": "status", "type": "enum(Accepted,Pending,Rejected)", "description": "Registration status", "required": True},
            ],
        },
    ]
    path = tmp_path / "schemas" / "all_schemas.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schemas, indent=2))
    return path


@pytest.fixture
def sample_appendices_json(tmp_path):
    """Create a sample appendices JSON file."""
    data = {
        "components": [
            {"component": "ChargingStation", "description": "Represents the entire charging station"},
            {"component": "EVSE", "description": "Electric Vehicle Supply Equipment"},
            {"component": "Connector", "description": "A connector on an EVSE"},
        ],
        "variables": [
            {"name": "Enabled", "data_type": "boolean", "unit": "", "description": "Whether the component is enabled", "component": "EVSE"},
            {"name": "Power", "data_type": "decimal", "unit": "W", "description": "Max power", "component": "EVSE"},
            {"name": "Model", "data_type": "string", "unit": "", "description": "Model name", "component": "ChargingStation"},
        ],
        "reason_codes": [
            {"group": "Transaction", "reason_code": "EVDisconnected", "description": "EV was disconnected"},
            {"group": "Transaction", "reason_code": "PowerLoss", "description": "Power was lost"},
        ],
        "security_events": [
            {"security_event": "FirmwareUpdated", "description": "Firmware was updated", "critical": "No"},
        ],
        "units_of_measure": [
            {"unit": "W", "description": "Watt"},
            {"unit": "Wh", "description": "Watt-hour"},
        ],
    }
    path = tmp_path / "appendices" / "all_appendices.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path
