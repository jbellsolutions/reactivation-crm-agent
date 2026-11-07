"""What we need from a new client, from the signup form or from the Factory's spec of a readout call.

The intake is the only client input any later step reads. Free text is the client's own words: it is
cleaned and length-capped here, and every template quotes it as data, never as instructions.
"""

import re
import unicodedata

LIST_TYPES = ("old_quotes", "past_customers", "no_shows", "lost_deals", "other")
CRMS = ("ghl", "attio", "zoho", "other")
PLAYS = ("reactivation", "lead_radar")
CONSENT = ("yes", "no", "unknown")
ORGO_PATHS = ("own", "invoicing")
MODEL_PROVIDERS = ("openrouter", "orgo-ai")
TEXT_MAX = 300

# What the voice intake asks (Justin, 2026-11-07): the business, what they sell and where, their CRM, their lists and
# text consent, and whether to add Lead Radar. The booking link, rep and time zone come at the setup call; the
# qualified-appointment criteria are ours to tell them; Orgo and the model aren't asked.
REQUIRED = (
    "business", "owner_first_name", "owner_email", "sells", "service_area", "lists", "crm", "plays", "agreement",
)
DEFAULTS = {"orgo": {"path": "own", "has_account": False}, "model": {"provider": "openrouter"}}


def complete(intake, offer):
    """The intake with what isn't asked filled in: the standard criteria, the default Orgo path and model."""
    out = {**DEFAULTS, **intake}
    out.setdefault("rep_first_name", intake.get("owner_first_name"))
    if not out.get("qualifying"):
        out["qualifying"] = list(offer["qualified_appointment"]["standard_criteria"])
    return out


def clean(text, limit=TEXT_MAX):
    """Strip control and format characters, collapse whitespace, cap the length."""
    text = "".join(ch for ch in str(text) if unicodedata.category(ch)[0] != "C" or ch in "\n\t")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower())
    return s.strip("-")[:40] or "client"


def validate(intake):
    """Every problem with an intake, as plain sentences. Empty means it's complete."""
    problems = [f"missing: {k}" for k in REQUIRED if intake.get(k) in (None, "", [], {})]
    if problems:
        return problems
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", intake["owner_email"]):
        problems.append("owner_email doesn't look like an email address")
    for key in ("website", "booking_link"):
        if intake.get(key) and not str(intake[key]).startswith("https://"):
            problems.append(f"{key} must start with https://")
    if intake.get("timezone"):
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(intake["timezone"])
        except Exception:
            problems.append(f"timezone {intake['timezone']!r} isn't an IANA zone like America/New_York")
    q = intake.get("qualifying")
    if q is not None and (not isinstance(q, list) or not all(clean(x) for x in q)):
        problems.append("qualifying must be a list of criteria for a qualified appointment")
    for i, lst in enumerate(intake["lists"]):
        if lst.get("type") not in LIST_TYPES:
            problems.append(f"lists[{i}].type must be one of {', '.join(LIST_TYPES)}")
        if lst.get("sms_consent") not in CONSENT:
            problems.append(f"lists[{i}].sms_consent must be yes, no or unknown")
    if intake["crm"].get("kind") not in CRMS:
        problems.append(f"crm.kind must be one of {', '.join(CRMS)}")
    plays = intake["plays"]
    if not plays or any(p not in PLAYS for p in plays):
        problems.append("plays must be reactivation and/or lead_radar")
    if (intake.get("orgo") or DEFAULTS["orgo"]).get("path") not in ORGO_PATHS:
        problems.append("orgo.path must be own (their Orgo account) or invoicing (our Orgo payment link)")
    if (intake.get("model") or DEFAULTS["model"]).get("provider") not in MODEL_PROVIDERS:
        problems.append("model.provider must be openrouter or orgo-ai")
    if intake["agreement"].get("accepted") is not True:
        problems.append("the agreement isn't accepted yet")
    return problems


def channels(intake):
    """Email for every list. Texts only for lists whose contacts gave written consent on record."""
    out = {}
    for lst in intake["lists"]:
        out[lst["type"]] = ["email", "sms"] if lst["sms_consent"] == "yes" else ["email"]
    return out


def profiles(intake, offer):
    names = []
    for play in intake["plays"]:
        for p in offer["plays"][play]["profiles"]:
            if p not in names:
                names.append(p)
    return names
