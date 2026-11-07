"""The appointment ledger: an append-only event file, the deposit drawn down per qualified appointment.

Events, one JSON object per line in `ledger/events.jsonl`:

    deposit     {at, usd, ref}                 the $500 down
    topup       {at, usd, ref}                 more credit
    adjust      {at, usd, note}                a credit or debit Justin makes by hand
    booked      {appt, contact, at, slot, evidence, last_purchase?}
    held        {appt, at, evidence}
    no_show     {appt, at}
    disposition {appt, at, qualified, reason?}  the client's mark
    charge      {appt, at, usd}                written only by settle()
    review      {at, choice}                   the day-90 decision: commission or per_appointment

A held appointment is qualified when the client marks it so, or when the dispute window passes with no
mark. It isn't qualified if it's a no-show, if the client marks it not qualified with a reason, if the same
contact already qualified inside the duplicate window, or if the contact bought inside the
existing-customer window. Charges are frozen as events, so a later rule change never rewrites a statement.
"""

import datetime as dt
import json
from pathlib import Path

UTC = dt.timezone.utc


def ts(value):
    t = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def read(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def append(path, event):
    if "type" not in event or "at" not in event:
        raise ValueError("an event needs a type and an at")
    with Path(path).open("a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")


def appointments(events, terms, now):
    """Each appointment's status and why, in slot order."""
    now = ts(now)
    appts, order = {}, []
    for e in events:
        a = e.get("appt")
        if e["type"] == "booked":
            appts[a] = {"appt": a, "contact": e["contact"], "slot": ts(e["slot"]), "booked_at": ts(e["at"]),
                        "last_purchase": ts(e["last_purchase"]) if e.get("last_purchase") else None,
                        "held": None, "no_show": False, "disposition": None, "charged": False,
                        "evidence": [e.get("evidence", "")]}
            order.append(a)
        elif a in appts:
            r = appts[a]
            if e["type"] == "held":
                r["held"] = ts(e["at"])
                r["evidence"].append(e.get("evidence", ""))
            elif e["type"] == "no_show":
                r["no_show"] = True
            elif e["type"] == "disposition":
                r["disposition"] = {"qualified": bool(e["qualified"]), "reason": e.get("reason", ""), "at": ts(e["at"])}
            elif e["type"] == "charge":
                r["charged"] = True

    window = dt.timedelta(hours=terms["dispute_hours"])
    dup = dt.timedelta(days=terms["duplicate_days"])
    existing = dt.timedelta(days=terms["existing_customer_days"])
    qualified_by_contact = {}
    out = []
    for a in sorted(order, key=lambda k: appts[k]["slot"]):
        r = appts[a]
        if r["charged"]:
            status, why = "charged", "qualified"
        elif r["no_show"]:
            status, why = "not_counted", "no_show"
        elif r["held"] is None:
            status, why = "pending", "not held yet"
        elif r["last_purchase"] and r["slot"] - r["last_purchase"] <= existing:
            status, why = "not_counted", "existing_customer"
        elif any(abs(r["slot"] - s) <= dup for s in qualified_by_contact.get(r["contact"], [])):
            status, why = "not_counted", "duplicate"
        elif r["disposition"] and not r["disposition"]["qualified"]:
            disputed_in_time = r["disposition"]["at"] <= r["held"] + window
            if disputed_in_time:
                status, why = "not_counted", r["disposition"]["reason"] or "fails_criteria"
            else:
                status, why = "qualified", "disputed after the window closed"
        elif r["disposition"] and r["disposition"]["qualified"]:
            status, why = "qualified", "client marked it qualified"
        elif now >= r["held"] + window:
            status, why = "qualified", "no dispute inside the window"
        else:
            status, why = "awaiting_window", f"dispute window open until {(r['held'] + window).isoformat()}"
        if status in ("qualified", "charged"):
            qualified_by_contact.setdefault(r["contact"], []).append(r["slot"])
        out.append({**r, "status": status, "why": why})
    return out


def credit(events):
    add = sum(float(e["usd"]) for e in events if e["type"] in ("deposit", "topup", "adjust"))
    spent = sum(float(e["usd"]) for e in events if e["type"] == "charge")
    return round(add - spent, 2)


def settle(path, terms, now):
    """Freeze a charge for every newly qualified appointment. Returns what was charged and where credit stands."""
    events = read(path)
    new = [r for r in appointments(events, terms, now) if r["status"] == "qualified"]
    for r in new:
        append(path, {"type": "charge", "at": ts(now).isoformat(), "appt": r["appt"], "usd": terms["price_usd"]})
    events = read(path)
    left = credit(events)
    return {"charged": [r["appt"] for r in new], "credit_usd": left,
            "balance_due_usd": round(max(0.0, -left), 2),
            "topup_needed": left < terms["price_usd"], "review_due": review_due(events, terms, now)}


def intro_ends(events, terms):
    deposits = [ts(e["at"]) for e in events if e["type"] == "deposit"]
    return min(deposits) + dt.timedelta(days=terms["intro_days"]) if deposits else None


def review_due(events, terms, now):
    end = intro_ends(events, terms)
    return bool(end and ts(now) >= end and not any(e["type"] == "review" for e in events))


def statement(path, terms, now, business="the client"):
    events = read(path)
    rows = appointments(events, terms, now)
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    left = credit(events)
    paid_in = sum(float(e["usd"]) for e in events if e["type"] in ("deposit", "topup", "adjust"))
    charged = [r for r in rows if r["status"] == "charged"]
    lines = [
        f"# Statement: {business}",
        "",
        f"As of {ts(now).date().isoformat()}. Price per qualified appointment: ${terms['price_usd']:,.2f}.",
        "",
        "| Appointment | Contact | When | Status | Why |",
        "|---|---|---|---|---|",
    ]
    lines += [f"| {r['appt']} | {r['contact']} | {r['slot'].date().isoformat()} | {r['status']} | {r['why']} |" for r in rows]
    lines += [
        "",
        f"- Credit paid in: ${paid_in:,.2f}",
        f"- Qualified and charged: {len(charged)}, ${len(charged) * terms['price_usd']:,.2f}",
        f"- Not counted: {counts.get('not_counted', 0)}; waiting on the dispute window: {counts.get('awaiting_window', 0)}; not held yet: {counts.get('pending', 0)}",
        f"- Credit left: ${max(left, 0):,.2f}" + (f"; balance due: ${-left:,.2f}" if left < 0 else ""),
    ]
    if left < terms["price_usd"]:
        lines.append("- **Top-up needed:** the credit can't cover the next qualified appointment.")
    if review_due(events, terms, now):
        lines.append("- **Day-90 review due:** commission, or stay per appointment.")
    return "\n".join(lines) + "\n"
