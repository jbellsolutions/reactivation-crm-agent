"""Self-serve signup to an intake: a paid Stripe Checkout session plus the intake form's answers.

    rcm signup --session <checkout session.json> --form <form row.json> --out <intake.json>

The session comes from the deposit's Stripe Payment Link (terms of service consent required, the card saved
for top-ups). The form row is the intake form's answers, flattened to plain values (a Notion form row, or any
form with the same field names). The two are matched on the owner's email. Nothing here calls a network:
fetching the session and the row is the poller's job, and their keys stay with it.
"""

import datetime as dt

from . import intake as intake_mod

LIST_FIELDS = {
    "old_quotes": ("old_quotes_count", "old_quotes_sms_consent"),
    "past_customers": ("past_customers_count", "past_customers_sms_consent"),
    "no_shows": ("no_shows_count", "no_shows_sms_consent"),
    "lost_deals": ("lost_deals_count", "lost_deals_sms_consent"),
}


class SignupError(ValueError):
    pass


def deposit_from_session(session, deposit_usd, form_accepted=False):
    if session.get("payment_status") != "paid":
        raise SignupError("the deposit session isn't paid")
    if int(session.get("amount_total") or 0) != int(round(deposit_usd * 100)):
        raise SignupError(f"the session charged {session.get('amount_total')} cents, not the ${deposit_usd:,.0f} deposit")
    # The agreement is accepted at checkout (Stripe's terms consent) or on the intake form; either one counts.
    if ((session.get("consent") or {}).get("terms_of_service")) != "accepted" and not form_accepted:
        raise SignupError("the agreement wasn't accepted, at checkout or on the intake form")
    paid_at = dt.datetime.fromtimestamp(int(session["created"]), dt.timezone.utc).isoformat()
    return {"paid": True, "paid_at": paid_at, "ref": session["id"]}


def intake_from(session, form, offer):
    email = ((session.get("customer_details") or {}).get("email") or "").strip().lower()
    if not email or email != str(form.get("owner_email", "")).strip().lower():
        raise SignupError("the form's email doesn't match the deposit's email")
    lists = []
    for kind, (count_key, consent_key) in LIST_FIELDS.items():
        count = int(form.get(count_key) or 0)
        if count > 0:
            lists.append({"type": kind, "source": form.get("crm_kind") or "csv", "approx_count": count,
                          "sms_consent": form.get(consent_key) or "unknown"})
    qualifying = [q.strip("-* ").strip() for q in str(form.get("qualifying", "")).splitlines() if q.strip("-* ").strip()]
    plays = form.get("plays") or ["reactivation"]
    if isinstance(plays, str):
        plays = [p.strip() for p in plays.split(",") if p.strip()]
    out = {
        "business": form.get("business"),
        "owner_first_name": form.get("owner_first_name"),
        "owner_full_name": form.get("owner_full_name") or "",
        "owner_email": email,
        "website": form.get("website"),
        "sells": form.get("sells"),
        "service_area": form.get("service_area"),
        "rep_first_name": form.get("rep_first_name") or form.get("owner_first_name"),
        "booking_link": form.get("booking_link"),
        "timezone": form.get("timezone"),
        "qualifying": qualifying,
        "lists": lists,
        "crm": {"kind": form.get("crm_kind") or "other", "name": form.get("crm_name") or ""},
        "plays": plays,
        "orgo": {"path": form.get("orgo_path") or "own", "has_account": bool(form.get("has_orgo"))},
        "model": {"provider": form.get("model_provider") or "openrouter"},
        "slack": bool(form.get("slack")),
        "agreement": {"accepted": True, "version": offer["version"], "ref": session["id"]},
        "deposit": deposit_from_session(session, offer["deposit_usd"], form.get("agreement_accepted") in (True, "true", "on", "yes")),
        "source": "self-serve",
    }
    problems = intake_mod.validate(out)
    if problems:
        raise SignupError("the form is incomplete: " + "; ".join(problems))
    return out
