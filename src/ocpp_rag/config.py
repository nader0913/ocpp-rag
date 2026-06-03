import os
from pathlib import Path

CACHE_DIR = Path(os.environ.get("OCPP_RAG_CACHE_DIR", Path.home() / ".cache" / "ocpp-rag"))
CHROMA_DIR = CACHE_DIR / "chroma_db"

COLLECTION_NAME = "ocpp_knowledge"

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
