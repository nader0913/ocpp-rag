from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SOURCE_DOCS_DIR = ROOT_DIR / "source_docs"
OUTPUT_DIR = ROOT_DIR / "output"
PARSED_DIR = OUTPUT_DIR / "parsed"
CHUNKS_DIR = OUTPUT_DIR / "chunks"
CHROMA_DIR = OUTPUT_DIR / "chroma_db"
SCHEMAS_DIR = OUTPUT_DIR / "schemas"
APPENDICES_DIR = OUTPUT_DIR / "appendices"

COLLECTION_NAME = "ocpp_knowledge"

OCPP_201_DOCS = {
    "ocpp201_part0": {
        "title": "OCPP 2.0.1 Part 0 - Introduction",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_part0_introduction.pdf",
        "ocpp_version": "2.0.1",
    },
    "ocpp201_part1": {
        "title": "OCPP 2.0.1 Part 1 - Architecture & Topology",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_part1_architecture_topology.pdf",
        "ocpp_version": "2.0.1",
    },
    "ocpp201_part2": {
        "title": "OCPP 2.0.1 Part 2 - Specification",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_part2_specification.pdf",
        "ocpp_version": "2.0.1",
    },
    "ocpp201_part2_appendices": {
        "title": "OCPP 2.0.1 Part 2 - Appendices",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_part2_appendices_v15.pdf",
        "ocpp_version": "2.0.1",
    },
    "ocpp201_part4": {
        "title": "OCPP 2.0.1 Part 4 - OCPP-J Specification",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_part4_ocpp-j-specification.pdf",
        "ocpp_version": "2.0.1",
    },
    "ocpp201_part5": {
        "title": "OCPP 2.0.1 Part 5 - Certification Profiles",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_part5_certification_profiles.pdf",
        "ocpp_version": "2.0.1",
    },
    "ocpp201_part6": {
        "title": "OCPP 2.0.1 Part 6 - Test Cases",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_part6-testcases.pdf",
        "ocpp_version": "2.0.1",
    },
    "ocpp201_errata": {
        "title": "OCPP 2.0.1 Edition 4 Errata (2026-04)",
        "file": "OCPP-2.0.1_all_files/OCPP-2.0.1_edition4_errata_2026-04.pdf",
        "ocpp_version": "2.0.1",
    },
}

OCPP_16_DOCS = {
    "ocpp16_spec": {
        "title": "OCPP 1.6 Specification",
        "file": "ocpp-1.6/ocpp-1.6.pdf",
        "ocpp_version": "1.6",
    },
    "ocpp16_j": {
        "title": "OCPP-J 1.6 Specification",
        "file": "ocpp-1.6/ocpp-j-1.6-specification.pdf",
        "ocpp_version": "1.6",
    },
}

OTHER_DOCS = {
    "pnc_whitepaper": {
        "title": "Using ISO 15118 Plug & Charge with OCPP 1.6",
        "file": "other/ocpp_1_6_ISO_15118_v10.pdf",
        "ocpp_version": None,
    },
}

ALL_DOCS = {**OCPP_201_DOCS, **OCPP_16_DOCS, **OTHER_DOCS}

FUNCTIONAL_BLOCKS = {
    "A": "Security",
    "B": "Provisioning",
    "C": "Authorization",
    "D": "LocalAuthorizationListManagement",
    "E": "Transactions",
    "F": "RemoteControl",
    "G": "Availability",
    "H": "Reservation",
    "I": "TariffAndCost",
    "J": "MeterValues",
    "K": "SmartCharging",
    "L": "FirmwareManagement",
    "M": "CertificateManagement",
    "N": "Diagnostics",
    "O": "DisplayMessage",
    "P": "DataTransfer",
}
