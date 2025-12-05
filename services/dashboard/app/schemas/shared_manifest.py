"""
Lightweight bridge to the canonical TypeScript/Zod schema bundle.

The JSON snapshot is sourced from packages/types/dist/schema.json, ensuring backend
enumerations stay aligned with the shared type package.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Set

SCHEMA_PATH = Path(__file__).resolve().parents[5] / "packages/types/dist/schema.json"


def _load_schema() -> Dict[str, Any]:
    if not SCHEMA_PATH.exists():
        return {}
    with SCHEMA_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


SCHEMA_SNAPSHOT = _load_schema()
SCHEMA_VERSION: str | None = SCHEMA_SNAPSHOT.get("version")
LEAD_STATUS_ENUM: Set[str] = set(
    SCHEMA_SNAPSHOT.get("definitions", {}).get("LeadStatus", {}).get("enum", [])
)
APPOINTMENT_OUTCOME_ENUM: Set[str] = set(
    SCHEMA_SNAPSHOT.get("definitions", {}).get("AppointmentOutcome", {}).get("enum", [])
)











