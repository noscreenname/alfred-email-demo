"""Loads ODCS v3.1 YAML contracts and exposes their field lists."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from config import CONTRACTS_DIR


@lru_cache(maxsize=None)
def load_contract(domain: str, mode_name: str) -> dict[str, Any]:
    path = Path(CONTRACTS_DIR) / f"{domain}_{mode_name}.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


def field_names(domain: str, mode_name: str) -> list[str]:
    contract = load_contract(domain, mode_name)
    fields: list[str] = []
    for block in contract.get("schema", []):
        for prop in block.get("properties", []):
            fields.append(prop["name"])
    return fields


def extended_field_names(domain: str) -> list[str]:
    contract = load_contract(domain, "extended")
    out: list[str] = []
    for block in contract.get("schema", []):
        for prop in block.get("properties", []):
            if prop.get("agent_specific"):
                out.append(prop["name"])
    return out
