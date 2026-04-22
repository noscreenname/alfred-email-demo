"""Alfred agent — load context per maturity level and run LLM."""

import json
from pathlib import Path

import anthropic
import yaml


DATA_DIR = Path(__file__).parent / "data"
PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_system_prompt() -> str:
    return (PROMPTS_DIR / "system.md").read_text()


def _read_json(path: Path) -> str:
    return path.read_text()


def _read_csv_as_text(path: Path) -> str:
    return path.read_text()


def _read_yaml_as_text(path: Path) -> str:
    return path.read_text()


def load_context(level: int, period: str) -> str:
    """Build the user-message context string for a given maturity level.

    Level 1: raw files dumped as-is — agent must infer relationships.
    Level 2: pre-joined curated product — relationships explicit.
    Level 3: curated product + ODCS contract — schema, quality, taxonomy provided.
    """
    level_dir = DATA_DIR / f"level-{level}"

    if level == 1:
        parts = [
            f"## Time period: {period}",
            "",
            "Below is the raw data from multiple sources. Use it to produce the inbox recap.",
            "",
            "### Gmail Inbox (raw API response with full message bodies)",
            _read_json(level_dir / "gmail.json"),
            "",
            "### Calendar (raw API response)",
            _read_json(level_dir / "calendar.json"),
        ]

        crm_path = level_dir / "crm.csv"
        if crm_path.exists():
            parts.extend([
                "",
                "### CRM Contacts (raw CSV export)",
                _read_csv_as_text(crm_path),
            ])

        parts.extend([
            "",
            "### Trello Tasks (raw API response)",
            _read_json(level_dir / "trello.json"),
        ])

    elif level == 2:
        parts = [
            f"## Time period: {period}",
            "",
            "Below is a curated data product combining email, calendar, CRM, and task data.",
            "Each email thread is pre-joined with sender contact info, related tasks, and calendar context.",
            "",
            "### Inbox Intelligence Product",
            _read_json(level_dir / "inbox-product.json"),
        ]

    elif level == 3:
        parts = [
            f"## Time period: {period}",
            "",
            "Below is a curated data product with its ODCS data contract.",
            "The contract defines the schema, quality rules, cross-source taxonomy mappings,",
            "and classification guidance. Use the contract to understand the data structure,",
            "validate data quality, and leverage taxonomy mappings for enriched classification.",
            "",
            "### Data Contract (ODCS)",
            _read_yaml_as_text(level_dir / "contract.yaml"),
            "",
            "### Inbox Intelligence Product (data)",
            _read_json(level_dir / "inbox-product.json"),
        ]

    else:
        raise ValueError(f"Unknown level: {level}")

    return "\n".join(parts)


def run_agent(system_prompt: str, context: str) -> dict:
    """Call the Anthropic API and return the recap with usage metrics.

    Returns dict with keys: content (str), input_tokens (int),
    output_tokens (int), context_chars (int).
    """
    client = anthropic.Anthropic()

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        temperature=0,
        system=system_prompt,
        messages=[
            {"role": "user", "content": context}
        ],
    )

    if not message.content:
        raise RuntimeError("LLM returned empty response")

    return {
        "content": message.content[0].text,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
        "context_chars": len(context),
    }


def validate_data_files():
    """Check that all required data files exist. Raises FileNotFoundError if any missing."""
    required = [
        DATA_DIR / "level-1" / "gmail.json",
        DATA_DIR / "level-1" / "calendar.json",
        DATA_DIR / "level-1" / "trello.json",
        DATA_DIR / "level-2" / "inbox-product.json",
        DATA_DIR / "level-3" / "inbox-product.json",
        DATA_DIR / "level-3" / "contract.yaml",
    ]

    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing required data files:\n" + "\n".join(f"  - {m}" for m in missing)
        )
