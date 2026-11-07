"""rcm: the Reactivation CRM Agent's command line.

    rcm signup --session <checkout session.json> --form <form row.json> --out <intake.json>
    rcm onboard <intake.json> --clients <root> [--readout <file>]
    rcm pack <client folder> [--out <dir>]
    rcm install <client folder> [--orgo orgo] [--profile <orgo profile>] [--apply] [--yes]
    rcm ledger <client folder> book --appt A1 --contact C1 --slot 2026-11-10T15:00 --evidence <link>
    rcm ledger <client folder> held|no-show --appt A1 [--evidence <link>]
    rcm ledger <client folder> mark --appt A1 --qualified yes|no [--reason outside_service_area]
    rcm ledger <client folder> settle|statement|review --choice commission
    rcm collect <client folder> [--orgo orgo] [--profile <orgo profile>]
"""

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from . import install, ledger, offer, onboard


def now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def client_terms(folder):
    m = json.loads((Path(folder) / "deliver" / "manifest.json").read_text())
    if not m["rcm"].get("terms"):
        raise SystemExit("no terms on this client yet: the price per qualified appointment isn't set")
    return m["rcm"]["terms"], m["label"]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="rcm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    o = sub.add_parser("onboard")
    o.add_argument("intake")
    o.add_argument("--clients", required=True)
    o.add_argument("--readout")

    i = sub.add_parser("install")
    i.add_argument("folder")
    i.add_argument("--orgo", default="orgo")
    i.add_argument("--profile")
    i.add_argument("--apply", action="store_true")
    i.add_argument("--yes", action="store_true")

    lg = sub.add_parser("ledger")
    lg.add_argument("folder")
    lg.add_argument("action", choices=["book", "held", "no-show", "mark", "settle", "statement", "review"])
    lg.add_argument("--appt")
    lg.add_argument("--contact")
    lg.add_argument("--slot")
    lg.add_argument("--evidence", default="")
    lg.add_argument("--qualified", choices=["yes", "no"])
    lg.add_argument("--reason", default="")
    lg.add_argument("--choice", choices=["commission", "per_appointment"])
    lg.add_argument("--at")

    pk = sub.add_parser("pack")
    pk.add_argument("folder")
    pk.add_argument("--out")

    sg = sub.add_parser("signup")
    sg.add_argument("--session", required=True)
    sg.add_argument("--form", required=True)
    sg.add_argument("--out", required=True)

    c = sub.add_parser("collect")
    c.add_argument("folder")
    c.add_argument("--orgo", default="orgo")
    c.add_argument("--profile")

    a = ap.parse_args(argv)

    if a.cmd == "onboard":
        res = onboard.onboard(json.loads(Path(a.intake).read_text()), a.clients, readout=a.readout)
        print(json.dumps(res, indent=2, default=str))
        return 0

    if a.cmd == "pack":
        print(onboard.pack(a.folder, a.out))
        return 0

    if a.cmd == "signup":
        from . import signup
        out = signup.intake_from(json.loads(Path(a.session).read_text()), json.loads(Path(a.form).read_text()),
                                 offer.load())
        Path(a.out).write_text(json.dumps(out, indent=2) + "\n")
        print(f"intake written to {a.out}")
        return 0

    if a.cmd == "install":
        for r in install.run(a.folder, a.orgo, a.profile, apply=a.apply, yes=a.yes):
            print(f"{r['result']:<18} {r['id']:<16} {r['who']}: {r['note'] or r['proof']}")
        return 0

    if a.cmd == "ledger":
        path = Path(a.folder) / "ledger" / "events.jsonl"
        at = a.at or now_iso()
        if a.action in ("book", "held", "no-show", "mark") and not a.appt:
            raise SystemExit("--appt is required")
        if a.action == "book":
            ledger.append(path, {"type": "booked", "at": at, "appt": a.appt, "contact": a.contact,
                                 "slot": a.slot, "evidence": a.evidence})
        elif a.action == "held":
            ledger.append(path, {"type": "held", "at": at, "appt": a.appt, "evidence": a.evidence})
        elif a.action == "no-show":
            ledger.append(path, {"type": "no_show", "at": at, "appt": a.appt})
        elif a.action == "mark":
            ledger.append(path, {"type": "disposition", "at": at, "appt": a.appt,
                                 "qualified": a.qualified == "yes", "reason": a.reason})
        elif a.action == "review":
            ledger.append(path, {"type": "review", "at": at, "choice": a.choice})
        else:
            terms, label = client_terms(a.folder)
            if a.action == "settle":
                print(json.dumps(ledger.settle(path, terms, at), indent=2))
            else:
                print(ledger.statement(path, terms, at, label))
        return 0

    if a.cmd == "collect":
        m = json.loads((Path(a.folder) / "deliver" / "manifest.json").read_text())
        base = [a.orgo] + (["--profile", a.profile] if a.profile else [])
        p = subprocess.run(base + ["computers", "bash", m["orgo"]["computer_name"], "-c",
                                   "cat /root/.rcm/ledger/events.jsonl"], capture_output=True, text=True)
        if p.returncode:
            raise SystemExit(f"couldn't read the client's ledger: {p.stderr.strip()[-300:]}")
        dest = Path(a.folder) / "ledger" / "events.jsonl"
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        for l in lines:
            json.loads(l)
        dest.write_text("\n".join(lines) + ("\n" if lines else ""))
        print(f"collected {len(lines)} events into {dest}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
