"""Fetch real data from Gmail (via MCP), Google Calendar (via MCP), and Trello (via API).

Usage:
    # Trello only (Gmail and Calendar require MCP tools in Claude Code):
    python fetch_real_data.py --trello

    # For Gmail and Calendar, use Claude Code with MCP tools:
    # The MCP fetch dumps data directly to data/level-1/gmail.json and calendar.json

Notes:
    - Gmail and Calendar data must be fetched via Claude Code MCP tools (not this script)
    - Trello data is fetched directly via REST API
    - CRM data is not available for real data — Level 1 handles its absence gracefully
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent / "data" / "level-1"


def fetch_trello():
    """Fetch all cards from open Trello boards and dump to trello.json."""
    key = os.getenv("TRELLO_API_KEY")
    token = os.getenv("TRELLO_API_TOKEN")

    if not key or not token:
        print("Error: TRELLO_API_KEY and TRELLO_API_TOKEN must be set in .env")
        sys.exit(1)

    base = "https://api.trello.com/1"

    def api(path):
        url = f"{base}{path}?key={key}&token={token}"
        with urlopen(url) as r:
            return json.loads(r.read())

    print("Fetching Trello boards...")
    boards = api("/members/me/boards")
    open_boards = [b for b in boards if not b["closed"]]
    print(f"  Found {len(open_boards)} open boards: {[b['name'] for b in open_boards]}")

    all_cards = []
    for board in open_boards:
        cards = api(f"/boards/{board['id']}/cards")
        for card in cards:
            all_cards.append({
                "id": card["id"],
                "name": card["name"],
                "board": board["name"],
                "list_id": card["idList"],
                "due": card.get("due"),
                "closed": card["closed"],
                "labels": [l["name"] for l in card.get("labels", []) if l.get("name")],
                "members": card.get("idMembers", []),
                "url": card.get("shortUrl"),
                "desc": card.get("desc", "")[:200],
            })

    output = DATA_DIR / "trello.json"
    with open(output, "w") as f:
        json.dump({"cards": all_cards}, f, indent=2, ensure_ascii=False)

    print(f"  Wrote {len(all_cards)} cards to {output}")


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if "--trello" in sys.argv or len(sys.argv) == 1:
        fetch_trello()

    print("\nDone. For Gmail and Calendar, use Claude Code MCP tools.")
    print("Then restart uvicorn to pick up the new data.")
