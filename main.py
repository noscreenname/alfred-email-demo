"""Alfred MVP — 3-level maturity comparison research rig."""

import time

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from alfred_agent import load_system_prompt, load_context, run_agent, validate_data_files

load_dotenv()

app = FastAPI(title="Alfred — Data Contract Maturity Demo")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

LEVELS = [
    {"number": 1, "name": "Level 1 — Raw APIs", "description": "Agent receives raw data files. Must infer relationships on its own."},
    {"number": 2, "name": "Level 2 — Data Product", "description": "Agent receives a curated, pre-joined dataset. Relationships are explicit."},
    {"number": 3, "name": "Level 3 — Data Contract", "description": "Agent receives the same dataset plus an ODCS contract with schema, quality rules, and taxonomy."},
]

SYSTEM_PROMPT = None


@app.on_event("startup")
def startup():
    global SYSTEM_PROMPT
    validate_data_files()
    SYSTEM_PROMPT = load_system_prompt()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "levels": LEVELS,
        "results": None,
        "comparison": None,
        "period": "week",
    })


VALID_PERIODS = {"day", "week", "month"}


def _build_comparison(results: list) -> dict:
    """Build a comparison structure matching emails across levels.

    Returns dict with:
      - emails: list of {key, subject, sender, levels: {1: {classification, reasoning}, ...}, has_diff}
      - summaries: {1: str, 2: str, 3: str}
      - stats: {1: {}, 2: {}, 3: {}}
    """
    summaries = {}
    stats = {}
    level_emails = {}

    for r in results:
        level = r["number"]
        parsed = r.get("parsed")
        if not parsed:
            continue

        summaries[level] = parsed.get("summary", "")
        stats[level] = parsed.get("stats", {})

        # Index emails by a key (sender_email + subject)
        level_emails[level] = {}
        for email in parsed.get("emails", []):
            key = f"{email.get('sender', '')}|{email.get('subject', '')}"
            level_emails[level][key] = email

    # Collect all unique email keys across all levels, preserving order from Level 1
    all_keys = []
    seen = set()
    for level in [1, 2, 3]:
        for key in level_emails.get(level, {}):
            if key not in seen:
                all_keys.append(key)
                seen.add(key)

    # Build comparison rows
    comparison_emails = []
    for key in all_keys:
        row = {
            "key": key,
            "subject": "",
            "sender": "",
            "sender_name": "",
            "date": "",
            "levels": {},
        }

        classifications = set()
        for level in [1, 2, 3]:
            email = level_emails.get(level, {}).get(key)
            if email:
                row["subject"] = row["subject"] or email.get("subject", "")
                row["sender"] = row["sender"] or email.get("sender", "")
                row["sender_name"] = row["sender_name"] or email.get("sender_name", "")
                row["date"] = row["date"] or email.get("date", "")
                row["levels"][level] = {
                    "classification": email.get("classification", "unknown"),
                    "reasoning": email.get("reasoning", ""),
                }
                classifications.add(email.get("classification"))
            else:
                row["levels"][level] = {
                    "classification": "missing",
                    "reasoning": "Email not present in this level's dataset",
                }
                classifications.add("missing")

        row["has_diff"] = len(classifications) > 1
        comparison_emails.append(row)

    return {
        "emails": comparison_emails,
        "summaries": summaries,
        "stats": stats,
    }


@app.post("/run", response_class=HTMLResponse)
async def run(request: Request, period: str = Form("week")):
    if period not in VALID_PERIODS:
        period = "week"
    results = []

    for level_info in LEVELS:
        level = level_info["number"]
        try:
            context = load_context(level, period)
            t0 = time.monotonic()
            result = run_agent(SYSTEM_PROMPT, context)
            elapsed = time.monotonic() - t0
            results.append({
                **level_info,
                "parsed": result["parsed"],
                "raw_response": result["raw"],
                "raw_context": context,
                "error": None,
                "metrics": {
                    "input_tokens": result["input_tokens"],
                    "output_tokens": result["output_tokens"],
                    "total_tokens": result["input_tokens"] + result["output_tokens"],
                    "context_chars": result["context_chars"],
                    "context_kb": round(result["context_chars"] / 1024, 1),
                    "processing_seconds": round(elapsed, 1),
                },
            })
        except Exception as e:
            results.append({
                **level_info,
                "parsed": None,
                "raw_response": None,
                "raw_context": None,
                "error": f"{type(e).__name__}: {e}",
                "metrics": None,
            })

    comparison = _build_comparison(results)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "levels": LEVELS,
        "results": results,
        "comparison": comparison,
        "period": period,
    })
