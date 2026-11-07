#!/usr/bin/env python3
"""The two remote setups behind self-serve signup, printed first and made only on --apply.

    python3 scripts/golive.py stripe  --signup-host <host>                 # the $500 deposit link, as API calls
    python3 scripts/golive.py stripe  --signup-host <host> --apply         # makes it (STRIPE_SECRET_KEY)
    python3 scripts/golive.py notion  --parent-page <Command Center page id>          # the Signups data source
    python3 scripts/golive.py notion  --parent-page <id> --apply           # makes it (NOTION_TOKEN)

Each one is a write to Justin's own Stripe or Notion, so --apply is run only on his yes (GO-LIVE.md 4 and 5).
Keys come from the environment or this repo's .env.local, and are never printed.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFER = json.loads((ROOT / "offer" / "offer.json").read_text())


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    p = ROOT / ".env.local"
    for line in (p.read_text().splitlines() if p.exists() else []):
        k, sep, v = line.strip().partition("=")
        if sep and k == name:
            return v.strip().strip('"').strip("'")
    raise SystemExit(f"{name} isn't set: add it with add-secret {name}")


def stripe_calls(host):
    """Product, price, Payment Link: terms consent required, the card saved for top-ups, redirect to intake."""
    cents = int(OFFER["deposit_usd"] * 100)
    return [
        ("products", {"name": "Reactivation CRM Agent deposit",
                      "description": "Credit toward qualified appointments, first 90 days."}),
        ("prices", {"product": "{product}", "currency": "usd", "unit_amount": str(cents)}),
        ("payment_links", {
            "line_items[0][price]": "{price}", "line_items[0][quantity]": "1",
            "consent_collection[terms_of_service]": "required",
            "payment_intent_data[setup_future_usage]": "off_session",
            "customer_creation": "always",
            "after_completion[type]": "redirect",
            "after_completion[redirect][url]": f"https://{host}/intake/?session_id={{CHECKOUT_SESSION_ID}}",
            "metadata[offer]": OFFER["id"], "metadata[offer_version]": OFFER["version"],
        }),
    ]


def signups_schema():
    sel = lambda *n: {"select": {"options": [{"name": x} for x in n]}}
    return {"Name": {"title": {}}, "Status": sel("new", "onboarded", "needs fix"), "Checkout session": {"rich_text": {}},
            "Intake": {"rich_text": {}}, "Source ID": {"rich_text": {}}, "Note": {"rich_text": {}}}


def post(url, headers, data=None, body=None):
    raw = urllib.parse.urlencode(data).encode() if data is not None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=raw, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["stripe", "notion"])
    ap.add_argument("--signup-host")
    ap.add_argument("--parent-page")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    if a.what == "stripe":
        if not a.signup_host:
            raise SystemExit("--signup-host is the signup site's host, for the redirect after payment")
        calls = stripe_calls(a.signup_host)
        if not a.apply:
            print(json.dumps([{"POST": f"/v1/{p}", "form": d} for p, d in calls], indent=2))
            print("\nNote: terms of service consent needs a terms URL in Stripe's public details first.", file=sys.stderr)
            return 0
        key = env("STRIPE_SECRET_KEY")
        h = {"Authorization": f"Bearer {key}"}
        made, url = {}, None
        for path, data in calls:
            data = {k: v.format(**made) if "{" in v and "CHECKOUT" not in v else v for k, v in data.items()}
            out = post(f"https://api.stripe.com/v1/{path}", h, data=data)
            made[path.rstrip("s")] = out["id"]
            url = out.get("url", url)
        print(json.dumps({**made, "url": url}, indent=2))
        print("Put the link's URL in web/public/config.js (paymentLink).", file=sys.stderr)
        return 0

    if not a.parent_page:
        raise SystemExit("--parent-page is the Command Center page the Signups database goes under")
    body = {"parent": {"type": "page_id", "page_id": a.parent_page},
            "title": [{"type": "text", "text": {"content": "Reactivation Signups"}}],
            "initial_data_source": {"properties": signups_schema()}}
    if not a.apply:
        print(json.dumps({"POST": "/v1/databases", "body": body}, indent=2))
        return 0
    out = post("https://api.notion.com/v1/databases", {"Authorization": f"Bearer {env('NOTION_TOKEN')}",
                                                         "Notion-Version": "2025-09-03", "Content-Type": "application/json"},
               body=body)
    print(json.dumps({"database": out.get("id"), "data_sources": [d.get("id") for d in out.get("data_sources", [])]}, indent=2))
    print("Set RCM_SIGNUPS_DS to the data source id, in the poller's .env.local and the signup site's settings.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
