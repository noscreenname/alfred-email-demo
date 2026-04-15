# Alfred — User Journey Examples

These journeys walk through the demo from the perspective of different users,
showing exactly what they click, what they see, and what they should take
away. Every journey uses the five seeded emails in `data/email_dataset.json`
and the two contract flavors (`standard` vs `extended`) toggled from the
top-right of the UI.

The goal of each journey is the same: make the invisible visible. Alfred's
behavior is not changing between journeys — the *contract* is, and that is
what causes the decision engine in `agent/decision.py` to short-circuit on
different signals.

---

## Persona cheat sheet

| Persona | Role | What they care about |
| --- | --- | --- |
| Priya | Data product manager | Whether agent-specific fields earn their keep |
| Marco | Platform architect | Whether the rule engine stays contract-agnostic |
| Dana | Compliance / risk lead | Whether autonomous replies are ever unsafe |
| Sam | Sales ops | Whether CRM deal state is respected |
| Lin | Developer extending Alfred | How to plug in a new domain |

---

## Journey 1 — Priya evaluates "is this contract extension worth it?"

**Goal.** Priya needs to justify, to a data governance committee, why Alfred's
contract should carry `classification_confidence`, `off_system_refs`,
`crm_open_deal`, and friends when ODCS v3.1 already covers the basics.

**Steps.**

1. Priya opens `http://localhost:8000`, sees the mock inbox on the left.
2. Top-right toggle is already on **`standard`**. She clicks
   `msg_003` — "As we discussed on the call last Thursday" from Marc Lefèvre.
3. The decision card on the right shows **ACT** — "Routine
   proposal-confirmation — drafting reply". A draft reply is generated.
4. She notices the **bottom callout**: *"In extended mode this decision would
   depend on `off_system_refs`, `thread_complete`."* She clicks it.
5. The toggle flips to **`extended`**. The decision re-runs live. The card
   now shows **ESCALATE** — "Email references off-system context — cannot
   verify prior commitment". The signals panel lights up the two fields she
   just saw named.
6. Priya opens `/log`, filters by `extended`, and screenshots the
   side-by-side.

**Takeaway.** Under the standard contract, Alfred would have auto-replied to
a message whose whole meaning lives in a phone call Alfred never saw. The
extended contract's `off_system_refs` field is the difference between a
confident reply and a correctly escalated human touch. Priya now has a
concrete, non-hypothetical example for her committee.

---

## Journey 2 — Marco verifies the architectural invariant

**Goal.** Marco is reviewing the PR that introduced "two modes." He is
suspicious that the rule engine has grown a hidden branch on
`mode == "extended"`.

**Steps.**

1. Marco clones the repo and runs the verification command from the README:
   ```bash
   grep -nE "standard|extended|mode" agent/decision.py
   ```
2. It returns nothing. Good.
3. He opens `agent/decision.py` and confirms each rule declares its
   `required_signals` and only reads view attributes, never a flag.
4. He opens the UI, picks `msg_001` (Sarah Chen, meeting request), toggles
   between standard and extended, and watches the decision card change *only*
   because signals became `None`, not because any code branched on mode.
5. For `msg_001` in **extended** mode, the decision is still **ACT** — but
   the "signals used" list now contains `data_age_minutes` / `safe_to_act` /
   `classification_confidence` where it previously showed only `label`.
6. He tails `/log` while clicking to confirm each decision is recorded with
   its mode, reason, and signals.

**Takeaway.** The engine really is contract-agnostic: behavior differences
come from data presence, not code paths. Marco approves the PR.

---

## Journey 3 — Dana stress-tests the unsafe-action failure modes

**Goal.** Dana's job is to find the case where Alfred sends something it
shouldn't. She will try every email and both modes and log anything that
looks wrong.

**Steps.**

1. Toggle **`extended`**. Walk the inbox top to bottom:
   - `msg_001` Sarah Chen → **ACT**, drafts reply. Calendar `safe_to_act=true`
     and confidence is high. OK.
   - `msg_002` Vendor.io follow-up → **ACT** (standard follow-up).
   - `msg_003` Marc Lefèvre "as we discussed" → **ESCALATE** via
     `off_system_refs`. 
   - `msg_004` Pascal Renard "questions before we sign" → **ESCALATE** via
     `crm_open_deal` + `deal_stage = negotiation`. 
   - `msg_005` Supplier EU invoice → **ESCALATE** (invoice requires human).
2. Toggle **`standard`**. Walk again:
   - `msg_003` now **ACT** with a draft reply. Dana flags this. The bottom
     callout tells her extended signals would have caught it.
   - `msg_004` now **ACT**. Dana flags this too — a live negotiation
     auto-reply is exactly the nightmare scenario.
3. She exports both runs from `/log` and attaches the comparison to her
   risk report.

**Takeaway.** The demo makes the risk concrete: two of five emails flip
from safe-to-answer to must-escalate when the contract surfaces the right
signal. Dana uses this to argue that the extended fields are not nice-to-have
but load-bearing for safety.

---

## Journey 4 — Sam pokes at the CRM deal-state interaction

**Goal.** Sam wants to see that Alfred respects the CRM pipeline. He focuses
on Pascal Renard (`msg_004`) because he knows that account has an open
renewal in negotiation.

**Steps.**

1. Open `msg_004` in **extended**. The decision card: **ESCALATE** — "Active
   deal in negotiation — autonomous reply suppressed". Signals used:
   `crm_open_deal`, `deal_stage`.
2. Sam opens the signals panel and sees every CRM field that the extended
   contract exposes rendered explicitly, including `deal_owner`.
3. He flips to **standard**. Same email, same sender. The CRM fields in the
   signals panel now render as red crosses — "not in contract". The decision
   card: **ACT**, drafting a reply.
4. Bottom callout: *"Would have depended on `crm_open_deal`, `deal_stage`."*
5. Sam clicks the callout to flip back to extended and confirms Alfred
   re-suppresses the autonomous reply.
6. He opens `data/crm_dataset.json` and notices the `_note` at the bottom:
   the deal pipeline lives in a separate system, which is why the contract
   has to be explicit about surfacing it.

**Takeaway.** The CRM deal signal is not implicit in "sender = known
contact." Without the extended contract's dedicated fields, Alfred has no
way to know a live negotiation is in flight, even though the contact record
itself is visible.

---

## Journey 5 — Lin adds a new data source

**Goal.** Lin wants to add a `tickets` domain (support tickets) so Alfred
can escalate when an email is tied to a customer with a `severity=high`
open ticket.

**Steps** (following `README.md` "Extending Alfred" section):

1. Drop `data/tickets_dataset.json` with a few rows.
2. Write `data/contracts/tickets_standard.yaml` (ticket id, subject, status)
   and `tickets_extended.yaml` (adds `severity`, `breach_risk`).
3. Create `contract/tickets_contract.py` with `TicketsContractView`
   and a `build_tickets_view(raw, flavor)` builder that nulls extended
   fields under the standard flavor.
4. Edit `agent/decision.py`:
   - Extend the `Rule` signature to accept the tickets view (or add it to the
     view bundle passed into predicates).
   - Add `_high_sev_ticket_pred` / `_decide` with
     `required_signals=["severity", "breach_risk"]`.
   - Insert it above `inform_only` in the `RULES` list.
   - Update `_all_signals_absent` so the new signal names map to the tickets
     source.
5. Wire `build_tickets_view` into `main.py`'s classify → view → decide
   pipeline.
6. Re-run `grep -nE "standard|extended|mode" agent/decision.py`. Still no
   output. Invariant preserved.
7. Click through the UI: the new ticket signals appear in the signals panel,
   and — critically — emails tied to a high-severity ticket flip from ACT in
   standard mode to ESCALATE in extended mode.

**Takeaway.** Lin has a recipe that is local, mechanical, and doesn't
require touching the rule-selection or mode-toggle logic. If the invariant
grep fails, she knows she accidentally leaked contract awareness into the
engine.

---

## Journey 6 — First-time visitor, five-minute tour

**Goal.** Someone just read the README and wants the "aha" in under five
minutes.

**Steps.**

1. Start the server, open `/`.
2. Click `msg_003` (Marc Lefèvre). Observe **ACT** + draft in standard mode.
3. Read the bottom callout. Click it.
4. Observe **ESCALATE** in extended mode.
5. Click `msg_004` (Pascal Renard). Observe **ESCALATE** in extended mode.
6. Toggle back to standard. Observe **ACT**.
7. Open `/log`. See two decisions per email — same data, different contract.

**Takeaway.** The visitor has now seen, in 90 seconds of clicking, the
entire point of the demo: *the contract is the interface; the agent behaves
exactly as well as the contract lets it.*
