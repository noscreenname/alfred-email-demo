"""Alfred configuration — loads .env, exposes constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CONTRACTS_DIR = DATA_DIR / "contracts"
DB_PATH = BASE_DIR / "alfred.db"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

CONTRACT_MODE = os.getenv("CONTRACT_MODE", "standard")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
CALENDAR_STALENESS_THRESHOLD_MINUTES = int(
    os.getenv("CALENDAR_STALENESS_THRESHOLD_MINUTES", "10")
)
GMAIL_MAX_MESSAGES = int(os.getenv("GMAIL_MAX_MESSAGES", "250"))
CALENDAR_DAYS_AHEAD = int(os.getenv("CALENDAR_DAYS_AHEAD", "14"))

_default_off_system = (
    "as we discussed,per our call,as agreed,following our conversation,"
    "as promised,like I mentioned,per my last email,comme convenu,"
    "suite a notre echange"
)
OFF_SYSTEM_PATTERNS = [
    p.strip().lower()
    for p in os.getenv("OFF_SYSTEM_PATTERNS", _default_off_system).split(",")
    if p.strip()
]

CLASSIFIER_MODEL = "claude-haiku-4-5-20251001"
RESPONDER_MODEL = "claude-sonnet-4-6"
