"""Signup to a ready client folder, with no person in the loop.

    rcm onboard <intake.json> --clients <Client Builds root> [--readout <recording or transcript>]

Writes one client record in the folder system (Clief form: a record with a pipeline inside it):

    <Client Builds>/<Business>/
      CONTEXT.md            the record's router: where it stands, what each folder is for
      NEEDS.md              what waits on a person, with who and why
      source/intake.json    the intake, as given
      source/inbox/         a readout recording or transcript, for `cb recordings` only; nothing here reads it
      deliver/charters/     the project charter, the agent charter, one charter per profile
      deliver/manifest.json the install manifest (the `fam launch` client manifest, plus this offer's block)
      deliver/INSTALL.md    the one line the client pastes, and what happens next
      ledger/events.jsonl   the appointment ledger, opened with the deposit if it's paid
      factory/outbox/builds-row.json   the Notion Builds row, in the Factory's shape, for its write-back

Re-running updates the rendered files and never touches the ledger or the inbox.
"""

import datetime as dt
import json
import re
import shutil
from pathlib import Path

from . import intake as intake_mod
from . import offer as offer_mod

KIT = offer_mod.ROOT / "kit"
CHARTERS = KIT / "charters"
ENGINE_LOCK = KIT / "engine.lock.json"
PLACEHOLDER = re.compile(r"\{\{([a-z_]+)\}\}")


class OnboardError(ValueError):
    pass


def render(template, values):
    missing = sorted({m for m in PLACEHOLDER.findall(template) if m not in values})
    if missing:
        raise OnboardError(f"template needs values for: {', '.join(missing)}")
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), template)


def values(intake, offer, today):
    c = intake_mod.clean
    lists = intake["lists"]
    chans = intake_mod.channels(intake)
    return {
        "business": c(intake["business"], 80),
        "owner_first_name": c(intake["owner_first_name"], 40),
        "rep_first_name": c(intake["rep_first_name"], 40),
        "sells": c(intake["sells"]),
        "service_area": c(intake["service_area"]),
        "booking_link": c(intake["booking_link"]),
        "timezone": intake["timezone"],
        "crm_kind": intake["crm"]["kind"],
        "crm_name": c(intake["crm"].get("name") or intake["crm"]["kind"], 40),
        "plays": ", ".join(intake["plays"]),
        "profiles": ", ".join(intake_mod.profiles(intake, offer)),
        "rendered_on": today.isoformat(),
        "list_summary": "; ".join(
            f"{l['type'].replace('_', ' ')} (about {int(l.get('approx_count') or 0):,})" for l in lists),
        "qualifying_list": "\n".join(f'- "{c(q)}"' for q in intake["qualifying"]),
        "qualifying_inline": "; ".join(f'"{c(q)}"' for q in intake["qualifying"]),
        "channel_list": "\n".join(f"- {t.replace('_', ' ')}: {', '.join(ch)}" for t, ch in chans.items()),
    }


def manifest(intake, offer, slug, agreed):
    """The `fam launch` client manifest (deploy/clients/example.json shape) plus this offer's block."""
    chans = intake_mod.channels(intake)
    texting = any("sms" in ch for ch in chans.values())
    crm = intake["crm"]["kind"]
    return {
        "client": slug,
        "label": intake_mod.clean(intake["business"], 80),
        "orgo": {"workspace_id": "", "computer_id": "", "computer_name": "Reactivation",
                 "path": intake["orgo"]["path"]},
        "data_mode": "client-data",
        "data_approval": {"approved": False, "record": ""},
        "ghl": {"location_name": "", "snapshot_id": "", "token_mode": "pit"} if crm == "ghl" else None,
        "imports": [{"type": l["type"], "source": l.get("source", crm), "sms_consent": l["sms_consent"]}
                    for l in intake["lists"]],
        "texting": texting,
        "calls": False,
        "slack": bool(intake.get("slack")),
        "access_received": {},
        "secrets": [
            {"key": "OPENROUTER_API_KEY", "required": intake["model"]["provider"] == "openrouter",
             "secret": True, "for": "the agents' model, on the client's own account"},
            {"key": "CRM_TOKEN", "required": crm in ("ghl", "attio", "zoho"), "secret": True,
             "for": "the agents' CRM token, without send rights"},
        ],
        "rcm": {
            "offer": offer["id"],
            "offer_version": offer["version"],
            "plays": intake["plays"],
            "profiles": intake_mod.profiles(intake, offer),
            "channels": chans,
            "terms": agreed,
            "booking_link": intake["booking_link"],
            "timezone": intake["timezone"],
            "owner_first_name": intake_mod.clean(intake["owner_first_name"], 40),
        },
    }


def builds_row(intake, slug, needs):
    """The Notion Builds row, in the properties the Factory writes (scripts/factory.py, Writeback)."""
    business = intake_mod.clean(intake["business"], 80)
    full = intake_mod.clean(intake.get("owner_full_name") or "", 80)
    # The Clients title the Notion sync links on is "Full Name, an em dash, Business" (references/factory.md).
    client_name = f"{full} \u2014 {business}" if full else business
    waiting = "; ".join(n["what"] for n in needs) or "nothing"
    if not full:
        waiting = "the roster sync to add this client; " + waiting
    return {
        "Build": f"Reactivation: {business}",
        "Client name": client_name,
        "Source ID": f"rcm:{slug}",
        # Builds' live options (the Factory's note, 2026-11-07): no Stage, because onboarding isn't a build
        # stage; Status paused while something waits, new when the install can start.
        "Status": "paused" if needs else "new",
        "Spend": 0,
        "Waiting on": waiting[:1900],
        "Product id": "reactivation-crm-agent",
    }


def needs_for(intake, terms_error, engine_pinned):
    out = []
    if terms_error:
        out.append({"who": "Justin", "what": "set the price per qualified appointment", "why": terms_error})
    if not (intake.get("deposit") or {}).get("paid"):
        out.append({"who": "client", "what": "pay the $500 deposit", "why": "the campaign starts on a paid deposit"})
    if any(l["sms_consent"] == "unknown" for l in intake["lists"]):
        out.append({"who": "client", "what": "confirm SMS consent per list",
                    "why": "lists marked unknown get email only until then"})
    if not engine_pinned:
        out.append({"who": "Justin", "what": "pin an engine release in kit/engine.lock.json",
                    "why": "the install stops at the engine step until a release exists (plan M1)"})
    out.append({"who": "client", "what": "approve the offer and the first messages once",
                "why": "nothing goes out before that"})
    return out


def onboard(intake, clients_root, offer=None, today=None, readout=None):
    offer = offer or offer_mod.load()
    today = today or dt.date.today()
    problems = intake_mod.validate(intake)
    if problems:
        raise OnboardError("intake incomplete: " + "; ".join(problems))
    slug = intake_mod.slug(intake["business"])
    name = re.sub(r"[^A-Za-z0-9 &'.-]+", "", intake_mod.clean(intake["business"], 60)).strip() or slug
    folder = Path(clients_root) / name
    for sub in ("source/inbox", "deliver/charters/profiles", "ledger", "factory/outbox"):
        (folder / sub).mkdir(parents=True, exist_ok=True)

    terms_error = None
    try:
        agreed = offer_mod.terms(offer, intake.get("agreed"))
    except offer_mod.OfferError as e:
        terms_error, agreed = str(e), None
    lock = json.loads(ENGINE_LOCK.read_text()) if ENGINE_LOCK.exists() else {}
    engine_pinned = bool(lock.get("sha256") and (lock.get("tag") or lock.get("bundle") == "pack"))
    needs = needs_for(intake, terms_error, engine_pinned)

    (folder / "source" / "intake.json").write_text(json.dumps(intake, indent=2) + "\n")
    if readout:
        dest = folder / "source" / "inbox" / Path(readout).name
        if not dest.exists():
            shutil.copy2(readout, dest)

    vals = values(intake, offer, today)
    out = folder / "deliver" / "charters"
    (out / "PROJECT-CHARTER.md").write_text(render((CHARTERS / "PROJECT-CHARTER.md").read_text(), vals))
    (out / "AGENT-CHARTER.md").write_text(render((CHARTERS / "AGENT-CHARTER.md").read_text(), vals))
    for p in intake_mod.profiles(intake, offer):
        (out / "profiles" / p).mkdir(parents=True, exist_ok=True)
        (out / "profiles" / p / "CHARTER.md").write_text(
            render((CHARTERS / "profiles" / p / "CHARTER.md").read_text(), vals))

    (folder / "deliver" / "manifest.json").write_text(
        json.dumps(manifest(intake, offer, slug, agreed), indent=2) + "\n")
    (folder / "deliver" / "INSTALL.md").write_text(install_doc(vals, slug))

    from . import ledger as ledger_mod
    ledger = folder / "ledger" / "events.jsonl"
    if not ledger.exists():
        ledger.write_text("")
    dep = intake.get("deposit") or {}
    already = any(e["type"] == "deposit" and e.get("ref") == dep.get("ref", "") for e in ledger_mod.read(ledger))
    if dep.get("paid") and agreed and not already:
        # Opened once the price is set: a signup that arrives before then gets its deposit on the re-run.
        ledger_mod.append(ledger, {"type": "deposit", "at": dep.get("paid_at") or today.isoformat(),
                                   "usd": agreed["deposit_usd"], "ref": dep.get("ref", "")})

    (folder / "factory" / "outbox" / "builds-row.json").write_text(
        json.dumps(builds_row(intake, slug, needs), indent=2, ensure_ascii=False) + "\n")
    (folder / "NEEDS.md").write_text(needs_doc(vals["business"], needs))
    (folder / "CONTEXT.md").write_text(context_doc(vals, slug, needs))
    return {"folder": str(folder), "slug": slug, "needs": needs, "terms": agreed}


def pack(folder, out_dir=None):
    """The client's own pack: `deliver/` only, zipped for the install email. Never `source/`, `ledger/` or notes."""
    import zipfile
    folder = Path(folder)
    out = Path(out_dir or folder / "factory" / "outbox") / f"{folder.name.replace(' ', '-')}-pack.zip"
    out.parent.mkdir(parents=True, exist_ok=True)
    lock = json.loads(ENGINE_LOCK.read_text()) if ENGINE_LOCK.exists() else {}
    engine = offer_mod.ROOT / "dist" / lock.get("file", "engine.tar.gz")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((folder / "deliver").rglob("*")):
            if f.is_file():
                z.write(f, Path("deliver") / f.relative_to(folder / "deliver"))
        if lock.get("bundle") == "pack" and engine.exists():
            # The engine travels in the paying client's own pack; the install checks its sha256 on the computer.
            z.write(engine, Path("deliver") / "engine" / engine.name)
    return out


def install_doc(v, slug):
    return f"""# Install: {v['business']}

Paste this into Claude Code on your computer:

```
Install the Reactivation CRM Agent for {v['business']} from https://github.com/jbellsolutions/reactivation-crm-agent and follow kit/INSTALL.md with client {slug}.
```

It walks you through each step and checks it:
1. Better than GrokBot, your window onto the agents (optional; skip it if you only want the agents).
2. Your Orgo computer: sign in, or buy one, from your own account.
3. The agents, their charters and the memory installed on that computer.
4. AI Guy support added to your Orgo workspace, so we can troubleshoot.
5. You sign in to {v['crm_name']} on the computer's screen. The agents never see your password.
6. A pass or fail check, with the fix for anything that fails.

Then you approve the offer and the first messages once, and the campaign starts.
"""


def needs_doc(business, needs):
    rows = "\n".join(f"| {n['who']} | {n['what']} | {n['why']} |" for n in needs)
    return f"# What {business} waits on\n\n| Who | What | Why |\n|---|---|---|\n{rows}\n"


def context_doc(v, slug, needs):
    return f"""# {v['business']}: reactivation record

Client `{slug}`. Product: Reactivation CRM Agent. Rendered by `rcm onboard`; edit `source/intake.json`, not these files.

| Folder | What |
|---|---|
| `source/` | The intake, and any readout call in `inbox/` for `cb recordings` |
| `deliver/` | Charters, the install manifest and the client's install line |
| `ledger/` | Every appointment and its evidence; the statement is built from it |
| `factory/outbox/` | The Builds row for Notion |
| `NEEDS.md` | {len(needs)} open item(s) |

Stages: signup, intake, record (this), install, check, approve copy, live, weekly statement, day-90 review.
"""
