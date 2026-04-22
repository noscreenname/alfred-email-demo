"""Alfred MVP — 3-level maturity comparison research rig."""

import time
import traceback

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import markdown

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
        "period": "week",
    })


VALID_PERIODS = {"day", "week", "month"}


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
            html = markdown.markdown(result["content"], extensions=["tables", "fenced_code"])
            results.append({
                **level_info,
                "content": html,
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
                "content": None,
                "raw_context": None,
                "error": f"{type(e).__name__}: {e}",
                "metrics": None,
            })

    return templates.TemplateResponse("index.html", {
        "request": request,
        "levels": LEVELS,
        "results": results,
        "period": period,
    })
