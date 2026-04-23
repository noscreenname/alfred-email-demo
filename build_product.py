"""Build Level 2 curated data product from Level 1 raw data.

Transforms raw Gmail, Calendar, and Trello dumps into a single
curated inbox-product.json with cleaned bodies, joined cross-source
context, and derived classification signals.

Usage:
    python build_product.py

Reads from:  data/level-1/gmail.json, calendar.json, trello.json
Writes to:   data/level-2/inbox-product.json
             data/level-3/inbox-product.json (identical copy)
"""

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
LEVEL_1 = DATA_DIR / "level-1"
LEVEL_2 = DATA_DIR / "level-2"
LEVEL_3 = DATA_DIR / "level-3"

# --- Sender type classification ---

AUTOMATED_DOMAINS = {
    "noreply", "no-reply", "do-not-reply", "ne-pas-repondre",
    "nepasrepondre", "notifications", "notification", "calendar-noreply",
    "receipts", "support", "feedback", "events", "sign", "alert", "alerts",
}

AUTOMATED_DOMAIN_PATTERNS = [
    r"noreply@", r"no-reply@", r"ne-pas-repondre@", r"nepasrepondre@",
    r"do-not-reply@", r"calendar-noreply@", r"notifications@",
    r"@accounts\.google\.com", r"@github\.com$",
]

TRANSACTIONAL_SENDERS = {
    "receipts-unitedkingdom@bolt.eu", "noreply@connect.sncf",
    "ne-pas-repondre@pasngr.ouigo.com", "noreply@eurostar.com",
    "eurostar@e.eurostar.com", "noreply@booking.com",
    "noreply@sosh.fr", "noreply@info.sncf-voyageurs.com",
    "info@mail.sncf-connect.com", "shipping@zalando.de",
    "owner-f5b311d4-368b-4461-becd-77a2c6480d05@messaging.lodgify.com",
    "sign@modelo.fr", "vepayet@citya.com",
}

NEWSLETTER_SENDERS = {
    "noreply@b.economist.com", "jakub@mail.leadershipintech.com",
    "nepasrepondre@citya.com", "contact@desertfest.be",
    "peter.deeley@neo4j.com", "LCL@message.lcl.fr",
    "communication@amiltone.com",
}


def classify_sender_type(email: str) -> str:
    """Classify sender as person, automated, newsletter, or transactional."""
    email_lower = email.lower()

    if email_lower in TRANSACTIONAL_SENDERS:
        return "transactional"

    if email_lower in NEWSLETTER_SENDERS:
        return "newsletter"

    for pattern in AUTOMATED_DOMAIN_PATTERNS:
        if re.search(pattern, email_lower):
            return "automated"

    local_part = email_lower.split("@")[0]
    if local_part in AUTOMATED_DOMAINS:
        return "automated"

    # Heuristic: if domain contains known automation patterns
    domain = email_lower.split("@")[1] if "@" in email_lower else ""
    if any(kw in domain for kw in ["luma-mail", "calendar", "engage.", "feedback."]):
        return "automated"

    return "person"


# --- Body cleaning ---

URL_PATTERN = re.compile(
    r'https?://\S{80,}',  # Long tracking URLs (80+ chars)
    re.IGNORECASE,
)

TRACKING_LINK_PATTERN = re.compile(
    r'\[https?://\S+\]',  # Markdown-style link wrappers [https://...]
    re.IGNORECASE,
)

UNSUBSCRIBE_PATTERN = re.compile(
    r'(^.*unsubscribe.*$|^.*se désabonner.*$|^.*désinscrire.*$)',
    re.IGNORECASE | re.MULTILINE,
)

FOOTER_PATTERNS = [
    re.compile(r'-{20,}.*', re.DOTALL),  # Separator lines followed by footer
    re.compile(r'This email was intended for.*', re.DOTALL | re.IGNORECASE),
    re.compile(r'You are receiving.*notification.*', re.DOTALL | re.IGNORECASE),
    re.compile(r'© \d{4}.*Corporation.*', re.DOTALL),
    re.compile(r'Pour nous contacter.*', re.DOTALL | re.IGNORECASE),
    re.compile(r'Vous recevez cette newsletter.*', re.DOTALL | re.IGNORECASE),
    re.compile(r'Si vous n.*arrivez pas.*visualiser.*', re.DOTALL | re.IGNORECASE),
]

EMPTY_LINES_PATTERN = re.compile(r'\n{4,}')


def clean_body(text: str | None) -> str:
    """Strip tracking URLs, HTML artifacts, unsubscribe footers, and noise."""
    if not text:
        return ""

    cleaned = text

    # Remove long tracking URLs
    cleaned = URL_PATTERN.sub("", cleaned)

    # Remove markdown-style link wrappers
    cleaned = TRACKING_LINK_PATTERN.sub("", cleaned)

    # Remove unsubscribe lines
    cleaned = UNSUBSCRIBE_PATTERN.sub("", cleaned)

    # Remove footer blocks
    for pattern in FOOTER_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Clean up whitespace
    cleaned = EMPTY_LINES_PATTERN.sub("\n\n", cleaned)
    cleaned = cleaned.strip()

    # Remove \r
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    return cleaned


# --- Action signal detection ---

ACTION_PATTERNS = [
    re.compile(r'\b(could you|can you|would you|please)\b', re.IGNORECASE),
    re.compile(r'\b(deadline|due date|by end of|avant le|d\'ici le)\b', re.IGNORECASE),
    re.compile(r'\b(urgent|asap|as soon as possible|dès que possible)\b', re.IGNORECASE),
    re.compile(r'\b(action required|action needed|requires? your)\b', re.IGNORECASE),
    re.compile(r'\b(sign|signer|approve|approuver|review|relire)\b', re.IGNORECASE),
    re.compile(r'\b(respond|reply|répondre|let me know|dites-moi)\b', re.IGNORECASE),
    re.compile(r'\?\s*$', re.MULTILINE),  # Ends with question mark
]


def has_action_signal(subject: str, body: str) -> bool:
    """Detect whether email contains signals requiring action."""
    text = f"{subject} {body}"
    return any(p.search(text) for p in ACTION_PATTERNS)


# --- Cross-source joining ---

def find_related_tasks(sender_name: str, sender_email: str, subject: str, trello_cards: list) -> list:
    """Find Trello cards related to this email by sender name or topic keywords."""
    related = []
    sender_words = set(sender_name.lower().split()) if sender_name else set()
    subject_words = set(re.findall(r'\w{4,}', subject.lower())) if subject else set()

    for card in trello_cards:
        card_words = set(re.findall(r'\w{4,}', card["name"].lower()))

        # Match by overlapping keywords (at least one meaningful word)
        overlap = (sender_words | subject_words) & card_words
        if overlap:
            related.append({
                "task_name": card["name"],
                "list": card["list"],
                "due": card.get("due"),
                "overdue": card.get("overdue", False),
                "match_reason": f"keyword match: {', '.join(overlap)}",
            })

    return related


def find_calendar_conflicts(subject: str, body: str, events: list) -> list:
    """Find calendar events that might conflict with meeting requests in the email."""
    conflicts = []

    # Simple heuristic: look for day/time mentions in email
    time_mentions = re.findall(
        r'(\d{1,2})\s*(?:h|:)\s*(\d{2})?\s*(am|pm|AM|PM|CET|CEST)?',
        f"{subject} {body}"
    )
    day_mentions = re.findall(
        r'(monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
        r'lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)',
        f"{subject} {body}",
        re.IGNORECASE,
    )

    # If email mentions times or days, check for same-day events
    if time_mentions or day_mentions:
        for event in events:
            conflicts.append({
                "event_name": event.get("summary", "Untitled"),
                "start": event.get("start"),
                "end": event.get("end"),
                "conflict_type": "potential_overlap",
            })

    return conflicts[:3]  # Limit to top 3 most relevant


def count_sender_history(sender_email: str, all_threads: list) -> int:
    """Count how many threads in the dataset are from this sender."""
    count = 0
    for thread in all_threads:
        for msg in thread.get("messages", []):
            if msg.get("sender", "").lower() == sender_email.lower():
                count += 1
                break  # Count thread once even if sender has multiple messages
    return count


# --- Main pipeline ---

def _classify_intensity(total_threads_1yr: int) -> str:
    """Classify relationship intensity based on 1-year message volume."""
    if total_threads_1yr >= 20:
        return "frequent"
    elif total_threads_1yr >= 5:
        return "regular"
    elif total_threads_1yr >= 2:
        return "occasional"
    else:
        return "rare"


def build_product():
    """Run the full data product pipeline."""
    # Load raw data
    with open(LEVEL_1 / "gmail.json") as f:
        gmail_data = json.load(f)
    with open(LEVEL_1 / "calendar.json") as f:
        calendar_data = json.load(f)
    with open(LEVEL_1 / "trello.json") as f:
        trello_data = json.load(f)

    # Load sender history (optional — may not exist yet)
    sender_history_path = LEVEL_1 / "sender-history.json"
    sender_history_map = {}
    if sender_history_path.exists():
        with open(sender_history_path) as f:
            history_data = json.load(f)
        for s in history_data.get("senders", []):
            sender_history_map[s["sender_email"].lower()] = s
        print(f"Sender history loaded: {len(sender_history_map)} senders")

    threads = gmail_data["threads"]
    events = calendar_data["events"]
    cards = trello_data["cards"]

    print(f"Raw data loaded: {len(threads)} threads, {len(events)} events, {len(cards)} cards")

    # Pre-compute sender frequency (within current dataset)
    sender_freq = {}
    for thread in threads:
        for msg in thread.get("messages", []):
            sender = msg.get("sender", "")
            if sender:
                sender_freq[sender.lower()] = sender_freq.get(sender.lower(), 0) + 1

    # Transform each thread
    product_threads = []
    for thread in threads:
        # Use the latest message in the thread
        latest_msg = thread["messages"][-1]
        sender_email = latest_msg.get("sender", "")
        sender_name = sender_email.split("@")[0].replace(".", " ").replace("-", " ").title()

        # Get full body from any message in thread that has one
        raw_body = ""
        for msg in thread["messages"]:
            if msg.get("plaintextBody"):
                raw_body = msg["plaintextBody"]
                break

        cleaned = clean_body(raw_body)
        subject = latest_msg.get("subject", "")

        # Cross-source joins
        related_tasks = find_related_tasks(sender_name, sender_email, subject, cards)
        calendar_conflicts = find_calendar_conflicts(subject, cleaned or latest_msg.get("snippet", ""), events)
        sender_history = count_sender_history(sender_email, threads)

        # Contact intelligence from sender history
        history = sender_history_map.get(sender_email.lower(), {})
        total_1yr = history.get("total_threads", 0)
        intensity = _classify_intensity(total_1yr)

        product_threads.append({
            "thread_id": thread["id"],
            "subject": subject,
            "date": latest_msg.get("date"),
            "snippet": latest_msg.get("snippet", ""),
            "body": cleaned,
            "is_unread": "UNREAD" in (latest_msg.get("labels") or []) if "labels" in latest_msg else True,
            "sender": {
                "name": sender_name,
                "email": sender_email,
                "type": classify_sender_type(sender_email),
            },
            "contact_intelligence": {
                "total_messages_1yr": total_1yr,
                "first_exchange": history.get("earliest_date"),
                "last_exchange": history.get("latest_date"),
                "intensity": intensity,
                "is_known_sender": total_1yr > 0,
            },
            "cross_source": {
                "related_tasks": related_tasks,
                "calendar_conflicts": calendar_conflicts,
                "sender_history_7d": sender_history,
            },
            "derived": {
                "has_action_signal": has_action_signal(subject, cleaned or latest_msg.get("snippet", "")),
                "has_related_task": len(related_tasks) > 0,
                "has_calendar_conflict": len(calendar_conflicts) > 0,
                "is_significant_sender": intensity in ("frequent", "regular"),
                "word_count": len(cleaned.split()) if cleaned else 0,
            },
        })

    # Build the product
    product = {
        "product": {
            "name": "Inbox Intelligence Product",
            "description": "Curated email threads enriched with cross-source context from Calendar, Trello, and 1-year Gmail sender history. Cleaned bodies, classified senders, contact intelligence, joined relationships, and derived action signals.",
            "owner": "data-platform-team",
            "source_data": {
                "gmail_threads": len(threads),
                "calendar_events": len(events),
                "trello_cards": len(cards),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "threads": product_threads,
    }

    # Write Level 2
    LEVEL_2.mkdir(parents=True, exist_ok=True)
    with open(LEVEL_2 / "inbox-product.json", "w") as f:
        json.dump(product, f, indent=2, ensure_ascii=False)

    # Copy to Level 3 (identical data, contract layered on top)
    LEVEL_3.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LEVEL_2 / "inbox-product.json", LEVEL_3 / "inbox-product.json")

    # Report
    size_kb = (LEVEL_2 / "inbox-product.json").stat().st_size / 1024
    action_count = sum(1 for t in product_threads if t["derived"]["has_action_signal"])
    task_match_count = sum(1 for t in product_threads if t["derived"]["has_related_task"])
    conflict_count = sum(1 for t in product_threads if t["derived"]["has_calendar_conflict"])
    person_count = sum(1 for t in product_threads if t["sender"]["type"] == "person")
    auto_count = sum(1 for t in product_threads if t["sender"]["type"] == "automated")

    print(f"\nProduct built: {len(product_threads)} threads ({size_kb:.1f} KB)")
    print(f"  Sender types: {person_count} person, {auto_count} automated, "
          f"{len(product_threads) - person_count - auto_count} other")
    print(f"  Action signals: {action_count} threads")
    print(f"  Related tasks: {task_match_count} threads matched to Trello cards")
    print(f"  Calendar conflicts: {conflict_count} threads")
    sig_sender_count = sum(1 for t in product_threads if t["derived"]["is_significant_sender"])
    print(f"  Significant senders (frequent/regular): {sig_sender_count} threads")
    print(f"\nWritten to:")
    print(f"  {LEVEL_2 / 'inbox-product.json'}")
    print(f"  {LEVEL_3 / 'inbox-product.json'} (identical copy)")


if __name__ == "__main__":
    build_product()
