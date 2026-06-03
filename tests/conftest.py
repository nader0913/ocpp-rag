import pytest


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
                "functional_block": "Provisioning",
                "use_case_id": "B01",
                "use_case_name": "Cold Boot Charging Station",
            },
        },
        {
            "content": "B01.FR.01: After start-up, send BootNotificationRequest.",
            "metadata": {
                "doc_id": "ocpp201_part2",
                "doc_title": "OCPP 2.0.1 Part 2",
                "ocpp_version": "2.0.1",
                "content_type": "requirements",
                "heading": "B01 - Cold Boot Charging Station - Requirements",
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
