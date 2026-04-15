"""Deterministic mock dataset generator for Alfred.

Emits:
  data/emails.json        ~250 messages
  data/calendar.json      ~120 events
  data/crm_contacts.json  30 contacts

Distributions (approx):
  - 5% VIP senders
  - 15% off-system-reference phrases in body
  - 20% open-deal contacts among non-VIPs
  - mix of labels: invoice, support, meeting-request, proposal-confirmation,
    newsletter, internal, personal
  - ~15% French bodies / senders
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 42
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

NUM_EMAILS = 250
NUM_EVENTS = 120
NUM_CONTACTS = 30

LABELS = [
    "invoice",
    "support",
    "meeting-request",
    "proposal-confirmation",
    "newsletter",
    "internal",
    "personal",
]

VIP_COMPANIES = ["Northwind Capital", "Ormond & Ashe", "Baleine Group"]
STANDARD_COMPANIES = [
    "Atlas Robotics", "Bluefin Data", "Cedar Studios", "Delta Foundry",
    "Echo Analytics", "Fjord Logistics", "Granite Legal", "Hearth Retail",
    "Ivy Biotech", "Juno Media", "Kestrel AI", "Luma Paints",
    "Maple Freight", "Nimbus Cloud", "Orchid Beauty", "Perch Finance",
    "Quill Press", "Rook Security", "Sable Hotels", "Tern Travel",
    "Umbra Design", "Vesper Wines", "Wren Timber",
]
FRENCH_COMPANIES = ["Garnier et Fils", "Libellule SA", "Maison Corbeau", "Atelier Vignes"]

FIRST_NAMES = [
    "Alice", "Marcus", "Priya", "Jonas", "Sofia", "Rahul", "Hana",
    "Mateo", "Noor", "Iris", "Felix", "Yara", "Omar", "Leila",
    "Theo", "Zara", "Rui", "Ines",
]
FRENCH_FIRST = ["Camille", "Julien", "Margaux", "Thibault", "Elodie", "Benoit"]
LAST_NAMES = ["Weber", "Osei", "Nakamura", "Bianchi", "Karlsson", "Oduya", "Park"]
FRENCH_LAST = ["Dupont", "Moreau", "Laurent", "Rousseau", "Fontaine"]

DEAL_STAGES = ["prospect", "qualified", "negotiation", "renewal", "at-risk", "closed-won"]
ACTIVE_STAGES = {"negotiation", "renewal", "at-risk"}

OFF_SYSTEM_PHRASES = [
    "As we discussed on the call yesterday",
    "Per our conversation last week",
    "Following our conversation Tuesday",
    "As agreed in our meeting",
    "Like I mentioned when we spoke",
    "Per my last email",
    "As promised",
    "Comme convenu lors de notre echange",
    "Suite a notre echange de ce matin",
]

# Body templates keyed by label.
TEMPLATES = {
    "invoice": [
        "Hi {first},\n\nAttached is invoice #{num} for {amount} EUR, due {due}. Let me know if you need a PO reference.\n\nThanks,\n{sender_first}",
        "Hello,\n\nFriendly reminder that invoice {num} ({amount} EUR) is due on {due}. Payment details unchanged.\n\nBest,\n{sender_first}",
        "Bonjour {first},\n\nVeuillez trouver ci-joint la facture {num} d'un montant de {amount} EUR, echeance le {due}.\n\nCordialement,\n{sender_first}",
    ],
    "support": [
        "Hi team,\n\nWe're seeing intermittent 500s on the export endpoint since this morning — about 1 in 20 requests. No config changes on our side. Ticket attached.\n\n{first}",
        "Hey,\n\nThe dashboard is stuck on 'loading' for our staging account. Cleared cache, tried two browsers. Any ideas?\n\nThanks,\n{first}",
        "Hello,\n\nCan you confirm whether the webhook retry policy changed last week? We saw a gap in deliveries between 02:00 and 03:00 UTC.\n\n{first}",
    ],
    "meeting-request": [
        "Hi {first},\n\nCould we grab 30 minutes this week to walk through Q2 numbers? Thursday or Friday afternoon works best on my side.\n\n{sender_first}",
        "Hello,\n\nWould you have time next Tuesday for a short sync on the rollout plan? Happy to send a calendar invite.\n\n{sender_first}",
        "Bonjour,\n\nSeriez-vous disponible jeudi prochain pour un point de 45 minutes sur le projet? Je m'adapte a votre agenda.\n\n{sender_first}",
    ],
    "proposal-confirmation": [
        "{offsys}. Can you confirm you're happy with the scope on page 3 of the proposal so we can countersign this week?\n\n{sender_first}",
        "Hi {first},\n\n{offsys}, sending over the signed SOW. Please counter-sign and we'll kick off Monday.\n\n{sender_first}",
        "{offsys}. Just need a thumbs up on the revised timeline and we're good to go.\n\n{sender_first}",
    ],
    "newsletter": [
        "This week in {company}: product updates, hiring news, and a deep dive into our new pricing page. Read online.",
        "Monthly digest — three new case studies, one podcast, and upcoming events in Berlin and Paris.",
    ],
    "internal": [
        "Team,\n\nReminder that all-hands is moved to Thursday 16:00 CET. Agenda in the shared doc.\n\n{sender_first}",
        "Hi all,\n\nPlease submit your OKR drafts by end of day Friday. Template link in the usual folder.\n\n{sender_first}",
    ],
    "personal": [
        "Hey {first}, are you free for coffee Saturday morning? There's a new place near the canal.",
        "Yo, still on for climbing Wednesday? I booked the 19:00 slot just in case.",
    ],
}

SUBJECTS = {
    "invoice": ["Invoice {num}", "Payment reminder — {num}", "Facture {num}"],
    "support": ["Export endpoint 500s", "Dashboard stuck loading", "Webhook delivery gap"],
    "meeting-request": ["Quick sync this week?", "30 min on Q2 numbers", "Point projet jeudi?"],
    "proposal-confirmation": ["Re: proposal — ready to sign", "SOW countersign", "Confirming scope"],
    "newsletter": ["{company} weekly", "Monthly digest"],
    "internal": ["All-hands moved", "OKR drafts due Friday"],
    "personal": ["Coffee Saturday?", "Climbing Wednesday"],
}


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def make_contacts(rng: random.Random) -> list[dict]:
    contacts: list[dict] = []
    # 2 VIPs
    for i in range(2):
        company = VIP_COMPANIES[i]
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        contacts.append({
            "contact_id": f"c{i+1:03d}",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@{company.lower().replace(' ', '').replace('&','and')}.com",
            "company": company,
            "sender_tier": "vip",
            "deals": [{
                "deal_id": f"d{i+1:03d}",
                "stage": rng.choice(list(ACTIVE_STAGES)),
                "owner": "Alex Vance",
                "value_eur": rng.randint(80, 400) * 1000,
            }],
        })
    # 6 open-deal standard clients
    for i in range(6):
        company = STANDARD_COMPANIES[i]
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        contacts.append({
            "contact_id": f"c{i+3:03d}",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@{company.lower().replace(' ', '')}.com",
            "company": company,
            "sender_tier": "standard-client",
            "deals": [{
                "deal_id": f"d{i+3:03d}",
                "stage": rng.choice(list(ACTIVE_STAGES)),
                "owner": rng.choice(["Alex Vance", "Priya Shah", "Jonas Becker"]),
                "value_eur": rng.randint(20, 150) * 1000,
            }],
        })
    # 4 French contacts (mix of standard-client / prospect)
    for i in range(4):
        company = FRENCH_COMPANIES[i]
        first = rng.choice(FRENCH_FIRST)
        last = rng.choice(FRENCH_LAST)
        tier = rng.choice(["standard-client", "prospect"])
        deals = []
        if tier == "standard-client" and rng.random() < 0.5:
            deals = [{
                "deal_id": f"d{i+9:03d}",
                "stage": rng.choice(DEAL_STAGES),
                "owner": "Camille Dupont",
                "value_eur": rng.randint(15, 90) * 1000,
            }]
        contacts.append({
            "contact_id": f"c{i+9:03d}",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@{company.lower().replace(' ', '').replace('et','')}.fr",
            "company": company,
            "sender_tier": tier,
            "deals": deals,
        })
    # Remaining standard/prospect contacts
    used_companies = {c["company"] for c in contacts}
    remaining_companies = [c for c in STANDARD_COMPANIES if c not in used_companies]
    needed = NUM_CONTACTS - len(contacts)
    for i, company in enumerate(remaining_companies[:needed]):
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)
        tier = rng.choice(["standard-client", "prospect", "standard-client"])
        contacts.append({
            "contact_id": f"c{len(contacts)+1:03d}",
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@{company.lower().replace(' ', '')}.com",
            "company": company,
            "sender_tier": tier,
            "deals": [],
        })
    return contacts[:NUM_CONTACTS]


def make_emails(rng: random.Random, contacts: list[dict]) -> list[dict]:
    emails = []
    now = datetime(2026, 4, 15, 9, 0, tzinfo=timezone.utc)
    for i in range(NUM_EMAILS):
        # 5% VIP, 35% known standard/prospect, 15% unknown french, rest unknown
        roll = rng.random()
        if roll < 0.05:
            sender = rng.choice([c for c in contacts if c["sender_tier"] == "vip"])
            from_name, from_email = sender["name"], sender["email"]
        elif roll < 0.55:
            sender = rng.choice([c for c in contacts if c["sender_tier"] != "vip"])
            from_name, from_email = sender["name"], sender["email"]
        else:
            # unknown sender
            if rng.random() < 0.3:
                first = rng.choice(FRENCH_FIRST); last = rng.choice(FRENCH_LAST)
                domain = rng.choice(["protonmail.com", "orange.fr", "gmail.com"])
            else:
                first = rng.choice(FIRST_NAMES); last = rng.choice(LAST_NAMES)
                domain = rng.choice(["gmail.com", "outlook.com", "fastmail.com"])
            from_name = f"{first} {last}"
            from_email = f"{first.lower()}.{last.lower()}@{domain}"

        label = rng.choices(
            LABELS,
            weights=[18, 18, 15, 10, 8, 15, 6],
            k=1,
        )[0]

        # Force some proposal-confirmation to align with VIP/open-deal senders
        subject_tpl = rng.choice(SUBJECTS[label])
        body_tpl = rng.choice(TEMPLATES[label])

        # ~15% off-system phrases — concentrate on proposal-confirmation
        include_offsys = label == "proposal-confirmation" or rng.random() < 0.08
        offsys = rng.choice(OFF_SYSTEM_PHRASES) if include_offsys else ""

        fmt = {
            "first": from_name.split()[0],
            "sender_first": "Alex",
            "num": f"INV-{2026000 + i}",
            "amount": f"{rng.randint(5, 95) * 100:,}",
            "due": (now + timedelta(days=rng.randint(5, 30))).strftime("%Y-%m-%d"),
            "company": from_email.split("@")[1].split(".")[0].title(),
            "offsys": offsys,
        }
        try:
            body = body_tpl.format(**fmt)
            subject = subject_tpl.format(**fmt)
        except KeyError:
            body = body_tpl
            subject = subject_tpl

        # If we wanted off-system but template didn't use {offsys}, prepend it.
        if include_offsys and offsys and offsys not in body:
            body = f"{offsys}. {body}"

        received = now - timedelta(minutes=rng.randint(5, 60 * 24 * 7))
        emails.append({
            "message_id": f"m{i+1:04d}",
            "from_name": from_name,
            "from_email": from_email,
            "subject": subject,
            "body": body,
            "label_hint": label,
            "received_at": iso(received),
            "thread_id": f"t{(i // 3) + 1:04d}",
            "thread_length": rng.randint(1, 4),
        })
    emails.sort(key=lambda e: e["received_at"], reverse=True)
    return emails


def make_calendar(rng: random.Random) -> list[dict]:
    events = []
    start = datetime(2026, 4, 15, 8, 0, tzinfo=timezone.utc)
    titles = [
        "Weekly staff sync", "Design review", "1:1 with Priya",
        "Customer onboarding — Cedar Studios", "Board prep",
        "Lunch — Atlas Robotics", "Demo: Kestrel AI", "Q2 planning",
        "Coffee with Camille", "Proposal walkthrough — Bluefin",
        "Renewal call — Northwind Capital", "Security review",
    ]
    for i in range(NUM_EVENTS):
        day_offset = rng.randint(-7, 14)
        hour = rng.randint(8, 18)
        begin = start + timedelta(days=day_offset, hours=hour - 8)
        duration = rng.choice([30, 45, 60, 90])
        events.append({
            "event_id": f"e{i+1:04d}",
            "title": rng.choice(titles),
            "start": iso(begin),
            "end": iso(begin + timedelta(minutes=duration)),
            "attendees": rng.randint(2, 8),
            "organizer": "alex.vance@alfred.demo",
        })
    events.sort(key=lambda e: e["start"])
    return events


def main() -> None:
    rng = random.Random(SEED)
    contacts = make_contacts(rng)
    emails = make_emails(rng, contacts)
    events = make_calendar(rng)

    (DATA_DIR / "crm_contacts.json").write_text(json.dumps(contacts, indent=2))
    (DATA_DIR / "emails.json").write_text(json.dumps(emails, indent=2))
    (DATA_DIR / "calendar.json").write_text(json.dumps(events, indent=2))
    print(f"Wrote {len(emails)} emails, {len(events)} events, {len(contacts)} contacts.")


if __name__ == "__main__":
    main()
