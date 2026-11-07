"""The poller: every new paid signup becomes a client record, with no person in the loop.

    rcm poll [--clients <Client Builds root>] [--write-builds]

Each run:
1. Reads the Reactivation Signups data source in Notion for rows whose Status is `new`. The intake page
   writes one row per form, holding the form's answers (Intake, JSON) and the Stripe Checkout session id.
2. Reads that Checkout session from Stripe (a restricted key that can only read sessions).
3. `rcm signup` checks the pair; a problem marks the row `needs fix` with the reason, and nothing else happens.
4. `rcm onboard` writes the client record and `rcm pack` its pack.
5. The install email is queued for the guarded sender, never sent from here.
6. With --write-builds, the client's Builds row is created or updated in Notion. Selects are checked against
   the live options (Status new or paused; no Stage, because onboarding isn't a build stage).
7. The signup row becomes `onboarded`, with the record's Source ID.

Config comes from the environment or this repo's `.env.local` (gitignored): NOTION_TOKEN, STRIPE_READ_KEY,
RCM_SIGNUPS_DS, RCM_BUILDS_DS (the Factory's Builds data source by default) and RCM_CLIENTS_ROOT.
"""

import json
import os
from pathlib import Path

from . import notion, offer as offer_mod, onboard, signup

BUILDS_DS = "413fd042-f076-4078-80fe-d588a20fc32d"
CONFIG_KEYS = ("NOTION_TOKEN", "STRIPE_READ_KEY", "RCM_SIGNUPS_DS", "RCM_BUILDS_DS", "RCM_CLIENTS_ROOT")


def config(env_file=offer_mod.ROOT / ".env.local"):
    cfg = {k: os.environ.get(k) for k in CONFIG_KEYS}
    p = Path(env_file)
    if p.exists():
        for line in p.read_text().splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and k in CONFIG_KEYS and not cfg.get(k):
                cfg[k] = v.strip().strip('"').strip("'")
    cfg["RCM_BUILDS_DS"] = cfg.get("RCM_BUILDS_DS") or BUILDS_DS
    return cfg


def missing(cfg):
    return [k for k in ("NOTION_TOKEN", "STRIPE_READ_KEY", "RCM_SIGNUPS_DS", "RCM_CLIENTS_ROOT") if not cfg.get(k)]


def install_email(intake, folder, pack_path):
    first = intake["owner_first_name"]
    body = (f"Hi {first},\n\nYou're in. Your pack is attached. Open Claude Code on your computer, unzip the pack, "
            f"and paste the line in its INSTALL.md. It walks you through the rest: your Orgo computer, the agents, "
            f"and signing in to your CRM on its screen.\n\nJustin")
    return {"bundle": "reactivation_install", "to": intake["owner_email"], "subject": "Your reactivation agent: install",
            "body": body, "attach": str(pack_path), "status": "draft", "template_approved": False}


def poll(api, cfg, offer=None, write_builds=False):
    offer = offer or offer_mod.load()
    report = {"onboarded": [], "needs_fix": [], "builds": [], "left_out": []}
    rows = api.query(cfg["RCM_SIGNUPS_DS"], {"property": "Status", "select": {"equals": "new"}})
    builds_schema = api.schema(cfg["RCM_BUILDS_DS"]) if write_builds else None
    signups_schema = api.schema(cfg["RCM_SIGNUPS_DS"])
    for page in rows:
        vals = notion.plain(page)
        try:
            form = json.loads(vals.get("Intake") or "{}")
            session = api.checkout_session(vals.get("Checkout session") or "")
            intake = signup.intake_from(session, form, offer)
        except (signup.SignupError, ValueError, RuntimeError) as e:
            p, _ = notion.props({"Status": "needs fix", "Note": str(e)}, signups_schema)
            api.update(page["id"], p)
            report["needs_fix"].append({"row": page["id"], "why": str(e)})
            continue
        res = onboard.onboard(intake, cfg["RCM_CLIENTS_ROOT"], offer)
        folder = Path(res["folder"])
        pack_path = onboard.pack(folder)
        outbox = folder / "factory" / "outbox"
        (outbox / "install-email.json").write_text(json.dumps(install_email(intake, folder, pack_path), indent=2) + "\n")
        row = json.loads((outbox / "builds-row.json").read_text())
        if write_builds:
            props, left = notion.props(row, builds_schema)
            found = api.query(cfg["RCM_BUILDS_DS"], {"property": "Source ID", "rich_text": {"equals": row["Source ID"]}})
            if found:
                api.update(found[0]["id"], props)
            else:
                api.create(cfg["RCM_BUILDS_DS"], props)
            report["builds"].append(row["Source ID"])
            report["left_out"] += [f"{row['Source ID']} {l}" for l in left]
        p, _ = notion.props({"Status": "onboarded", "Source ID": row["Source ID"], "Note": f"record: {folder}"},
                            signups_schema)
        api.update(page["id"], p)
        report["onboarded"].append(row["Source ID"])
    return report
