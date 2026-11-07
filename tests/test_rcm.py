"""Offline tests: python3 -m unittest discover tests"""

import copy
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from rcm import install, intake, ledger, notion, offer, onboard, poll, signup  # noqa: E402

EXAMPLE = ROOT / "examples" / "synthetic-client"
TERMS = {"price_usd": 100.0, "deposit_usd": 500.0, "intro_days": 90, "dispute_hours": 72,
         "duplicate_days": 90, "existing_customer_days": 60}

STUB_ORGO = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["ORGO_LOG"], "a") as f:
    f.write(json.dumps(args + ["KEY=" + ("set" if os.environ.get("ORGO_API_KEY") == "test-key-not-real" else "unset")]) + "\\n")
if "whoami" in args:
    print(json.dumps({"email": "dana@example.com"}))
elif args[-2:] == ["computers", "list"]:
    print(os.environ.get("ORGO_COMPUTERS", "[]"))
sys.exit(0)
"""


def sample():
    return json.loads((EXAMPLE / "intake.json").read_text())


class IntakeTests(unittest.TestCase):
    def test_complete_intake_passes(self):
        self.assertEqual(intake.validate(sample()), [])

    def test_missing_and_bad_fields_are_named(self):
        bad = sample()
        del bad["booking_link"]
        self.assertIn("missing: booking_link", intake.validate(bad))
        bad = sample()
        bad["website"] = "http://example.com"
        bad["lists"][0]["sms_consent"] = "maybe"
        bad["agreement"]["accepted"] = False
        problems = " ".join(intake.validate(bad))
        self.assertIn("website must start with https://", problems)
        self.assertIn("sms_consent", problems)
        self.assertIn("agreement isn't accepted", problems)

    def test_texts_only_where_consent_is_on_record(self):
        self.assertEqual(intake.channels(sample()), {"old_quotes": ["email", "sms"], "past_customers": ["email"]})

    def test_free_text_is_cleaned(self):
        self.assertEqual(intake.clean("a​b\x00 c\n\n d" + "x" * 400)[:6], "ab c d")
        self.assertLessEqual(len(intake.clean("y" * 1000)), intake.TEXT_MAX)


class SignupTests(unittest.TestCase):
    def load(self, name):
        return json.loads((EXAMPLE / name).read_text())

    def test_paid_session_and_form_make_a_valid_intake(self):
        out = signup.intake_from(self.load("checkout-session.json"), self.load("form-row.json"), offer.load())
        self.assertEqual(intake.validate(out), [])
        self.assertEqual(out["deposit"]["ref"], "cs_test_synthetic0001")
        self.assertEqual(out["qualifying"], ["Owns the home", "Inside the service area", "Roof is 10 years or older"])
        self.assertEqual([l["type"] for l in out["lists"]], ["old_quotes", "past_customers"])

    def test_unpaid_wrong_amount_or_no_consent_is_refused(self):
        form = self.load("form-row.json")
        for change in ({"payment_status": "unpaid"}, {"amount_total": 100}, {"consent": {}}):
            s = {**self.load("checkout-session.json"), **change}
            with self.assertRaises(signup.SignupError):
                signup.intake_from(s, form, offer.load())

    def test_email_must_match(self):
        form = {**self.load("form-row.json"), "owner_email": "someone@example.org"}
        with self.assertRaises(signup.SignupError):
            signup.intake_from(self.load("checkout-session.json"), form, offer.load())


def sel(*names):
    return {"type": "select", "select": {"options": [{"name": n} for n in names]}}


TXT, TITLE = {"type": "rich_text"}, {"type": "title"}
SIGNUPS = {"Name": TITLE, "Status": sel("new", "needs price", "onboarded", "needs fix"), "Checkout session": TXT,
           "Intake": TXT, "Source ID": TXT, "Note": TXT, "Price": {"type": "number"}}
BUILDS = {"Build": TITLE, "Client name": TXT, "Source ID": TXT, "Waiting on": TXT, "Product id": TXT,
          "Spend": {"type": "number"}, "Status": sel("new", "running", "paused", "stopped", "failed", "done"),
          "Stage": sel("spec", "understand", "design", "build", "review", "fix", "walk", "package")}


class FakeNotionStripe:
    """Stands in for Notion's data sources and Stripe's Checkout sessions. Records every write."""

    def __init__(self, rows, sessions):
        self.rows, self.sessions, self.writes, self.builds = rows, sessions, [], []

    def __call__(self, method, url, headers, body):
        if url.startswith(notion.STRIPE):
            sid = url.rsplit("/", 1)[1]
            return (200, self.sessions[sid]) if sid in self.sessions else (404, {"error": {"message": "no such session"}})
        path = url[len(notion.NOTION):]
        if method == "GET" and path == "/data_sources/signups":
            return 200, {"properties": SIGNUPS}
        if method == "GET" and path == "/data_sources/builds":
            return 200, {"properties": BUILDS}
        if method == "POST" and path == "/data_sources/signups/query":
            wanted = {f["select"]["equals"] for f in body["filter"]["or"]}
            return 200, {"results": [self.page(r) for r in self.rows if r["status"] in wanted], "has_more": False}
        if method == "POST" and path == "/data_sources/builds/query":
            sid = body["filter"]["rich_text"]["equals"]
            return 200, {"results": [{"id": b["id"]} for b in self.builds if b["sid"] == sid], "has_more": False}
        if method == "POST" and path == "/pages":
            self.writes.append(("create", body))
            sid = body["properties"]["Source ID"]["rich_text"][0]["text"]["content"]
            self.builds.append({"id": f"b{len(self.builds)}", "sid": sid})
            return 200, {"id": f"b{len(self.builds)}"}
        if method == "PATCH" and path.startswith("/pages/"):
            pid = path.split("/")[2]
            self.writes.append(("update", pid, body))
            for r in self.rows:
                if r["id"] == pid and "Status" in body["properties"]:
                    r["status"] = body["properties"]["Status"]["select"]["name"]
            return 200, {"id": pid}
        return 404, {"message": f"unexpected {method} {path}"}

    @staticmethod
    def page(r):
        def t(v):
            return {"type": "rich_text", "rich_text": [{"plain_text": v}]}
        return {"id": r["id"], "properties": {"Name": {"type": "title", "title": [{"plain_text": r["form"].get("business", "")}]},
                                               "Status": {"type": "select", "select": {"name": r["status"]}},
                                               "Checkout session": t(r["session"]), "Intake": t(json.dumps(r["form"])),
                                               "Price": {"type": "number", "number": r.get("price")}}}


class PollTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        form = json.loads((EXAMPLE / "form-row.json").read_text())
        session = json.loads((EXAMPLE / "checkout-session.json").read_text())
        bad = {**form, "owner_email": "someone@example.org", "business": "Mismatch Test Co"}
        self.fake = FakeNotionStripe(
            [{"id": "r1", "status": "new", "session": session["id"], "form": form, "price": 120},
             {"id": "r2", "status": "new", "session": session["id"], "form": bad}],
            {session["id"]: session})
        self.cfg = {"NOTION_TOKEN": "t", "STRIPE_READ_KEY": "k", "RCM_SIGNUPS_DS": "signups",
                    "RCM_BUILDS_DS": "builds", "RCM_CLIENTS_ROOT": str(self.tmp / "clients")}
        self.api = notion.Api("t", "k", http=self.fake)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_a_paid_signup_becomes_a_record_and_a_builds_row(self):
        out = poll.poll(self.api, self.cfg, write_builds=True)
        self.assertEqual(out["onboarded"], ["rcm:harbor-test-roofing"])
        self.assertEqual([n["row"] for n in out["needs_fix"]], ["r2"])
        folder = self.tmp / "clients" / "Harbor Test Roofing"
        mail = json.loads((folder / "factory" / "outbox" / "install-email.json").read_text())
        self.assertEqual((mail["to"], mail["status"], mail["template_approved"]), ("dana@example.com", "draft", False))
        self.assertTrue(Path(mail["attach"]).exists())
        create = next(w for w in self.fake.writes if w[0] == "create")[1]
        self.assertEqual(create["parent"], {"data_source_id": "builds"})
        self.assertEqual(create["properties"]["Status"], {"select": {"name": "paused"}})
        self.assertNotIn("Stage", create["properties"])
        self.assertEqual({r["id"]: r["status"] for r in self.fake.rows}, {"r1": "onboarded", "r2": "needs fix"})

    def test_a_second_run_does_nothing_new(self):
        poll.poll(self.api, self.cfg, write_builds=True)
        writes = len(self.fake.writes)
        out = poll.poll(self.api, self.cfg, write_builds=True)
        self.assertEqual((out["onboarded"], out["needs_fix"]), ([], []))
        self.assertEqual(len(self.fake.writes), writes)

    def test_without_write_builds_nothing_reaches_builds(self):
        poll.poll(self.api, self.cfg)
        self.assertFalse([w for w in self.fake.writes if w[0] == "create"])

    def test_no_price_waits_then_finishes_when_price_is_filled(self):
        self.fake.rows[0]["price"] = None
        out = poll.poll(self.api, self.cfg)
        self.assertEqual((out["onboarded"], out["needs_price"]), ([], ["rcm:harbor-test-roofing"]))
        path = self.tmp / "clients" / "Harbor Test Roofing" / "ledger" / "events.jsonl"
        self.assertEqual(ledger.read(path), [])
        self.fake.rows[0]["price"] = 150
        out = poll.poll(self.api, self.cfg)
        self.assertEqual(out["onboarded"], ["rcm:harbor-test-roofing"])
        self.assertEqual([e["type"] for e in ledger.read(path)], ["deposit"])
        m = json.loads((self.tmp / "clients" / "Harbor Test Roofing" / "deliver" / "manifest.json").read_text())
        self.assertEqual(m["rcm"]["terms"]["price_usd"], 150.0)

    def test_an_option_the_database_lacks_is_left_out_not_created(self):
        props, left = notion.props({"Status": "waiting", "Stage": "onboard", "Build": "x"}, BUILDS)
        self.assertEqual(list(props), ["Build"])
        self.assertEqual(len(left), 2)


class OfferTests(unittest.TestCase):
    def test_no_price_means_no_terms(self):
        with self.assertRaises(offer.OfferError):
            offer.terms(offer.load())

    def test_agreed_price_makes_terms(self):
        t = offer.terms(offer.load(), {"price_per_appointment_usd": 100})
        self.assertEqual((t["price_usd"], t["deposit_usd"], t["intro_days"]), (100.0, 500.0, 90))


class OnboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_signup_becomes_a_ready_record(self):
        res = onboard.onboard(sample(), self.tmp, readout=EXAMPLE / "readout-stub.txt")
        folder = Path(res["folder"])
        charters = folder / "deliver" / "charters"
        for p in ("PROJECT-CHARTER.md", "AGENT-CHARTER.md", "profiles/reactivation/CHARTER.md",
                  "profiles/reply/CHARTER.md", "profiles/sales/CHARTER.md", "profiles/deal/CHARTER.md",
                  "profiles/radar/CHARTER.md"):
            text = (charters / p).read_text()
            self.assertNotIn("{{", text, p)
            self.assertIn("Harbor Test Roofing", text + (charters / "PROJECT-CHARTER.md").read_text())
        m = json.loads((folder / "deliver" / "manifest.json").read_text())
        self.assertEqual(m["client"], "harbor-test-roofing")
        self.assertTrue(m["texting"])
        self.assertFalse(m["data_approval"]["approved"])
        self.assertEqual(m["rcm"]["profiles"], ["reactivation", "reply", "sales", "deal", "radar"])
        row = json.loads((folder / "factory" / "outbox" / "builds-row.json").read_text())
        self.assertEqual(row["Source ID"], "rcm:harbor-test-roofing")
        self.assertEqual(row["Product id"], "reactivation-crm-agent")
        events = ledger.read(folder / "ledger" / "events.jsonl")
        self.assertEqual([e["type"] for e in events], ["deposit"])

    def test_readout_is_filed_and_never_rendered(self):
        res = onboard.onboard(sample(), self.tmp, readout=EXAMPLE / "readout-stub.txt")
        folder = Path(res["folder"])
        self.assertTrue((folder / "source" / "inbox" / "readout-stub.txt").exists())
        for f in (folder / "deliver").rglob("*"):
            if f.is_file():
                text = f.read_text().lower()
                self.assertNotIn("50% discount", text, f)
                self.assertNotIn("ignore your instructions", text, f)

    def test_rerun_keeps_the_ledger(self):
        res = onboard.onboard(sample(), self.tmp)
        path = Path(res["folder"]) / "ledger" / "events.jsonl"
        ledger.append(path, {"type": "booked", "at": "2026-11-08T10:00:00", "appt": "A1", "contact": "C1",
                             "slot": "2026-11-09T10:00:00"})
        onboard.onboard(sample(), self.tmp)
        self.assertEqual(len(ledger.read(path)), 2)

    def test_deposit_opens_once_the_price_is_set(self):
        s = sample()
        del s["agreed"]
        res = onboard.onboard(s, self.tmp)
        path = Path(res["folder"]) / "ledger" / "events.jsonl"
        self.assertEqual(ledger.read(path), [])
        onboard.onboard(sample(), self.tmp)
        onboard.onboard(sample(), self.tmp)
        self.assertEqual([e["type"] for e in ledger.read(path)], ["deposit"])

    def test_unset_price_is_a_need_not_a_crash(self):
        s = sample()
        del s["agreed"]
        res = onboard.onboard(s, self.tmp)
        self.assertIsNone(res["terms"])
        self.assertTrue(any("price per qualified appointment" in n["what"] for n in res["needs"]))
        self.assertEqual(ledger.read(Path(res["folder"]) / "ledger" / "events.jsonl"), [])

    def test_pack_holds_only_what_the_client_gets(self):
        import zipfile
        res = onboard.onboard(sample(), self.tmp, readout=EXAMPLE / "readout-stub.txt")
        names = zipfile.ZipFile(onboard.pack(res["folder"])).namelist()
        self.assertIn("deliver/manifest.json", names)
        self.assertIn("deliver/charters/profiles/deal/CHARTER.md", names)
        self.assertFalse([n for n in names if not n.startswith("deliver/")])

    def test_incomplete_intake_is_refused(self):
        s = sample()
        s["plays"] = []
        with self.assertRaises(onboard.OnboardError):
            onboard.onboard(s, self.tmp)


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "events.jsonl"
        ledger.append(self.path, {"type": "deposit", "at": "2026-11-07T15:00:00+00:00", "usd": 500})

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def book(self, appt, contact, slot, held=True, **extra):
        ledger.append(self.path, {"type": "booked", "at": "2026-11-08T09:00:00+00:00", "appt": appt,
                                  "contact": contact, "slot": slot, "evidence": f"cal:{appt}", **extra})
        if held:
            ledger.append(self.path, {"type": "held", "at": slot, "appt": appt, "evidence": f"meet:{appt}"})

    def status(self, now):
        return {r["appt"]: (r["status"], r["why"]) for r in ledger.appointments(ledger.read(self.path), TERMS, now)}

    def test_every_rule(self):
        self.book("A1", "C1", "2026-11-10T15:00:00+00:00")
        ledger.append(self.path, {"type": "disposition", "at": "2026-11-10T18:00:00+00:00", "appt": "A1", "qualified": True})
        self.book("A2", "C2", "2026-11-10T16:00:00+00:00", held=False)
        ledger.append(self.path, {"type": "no_show", "at": "2026-11-10T16:30:00+00:00", "appt": "A2"})
        self.book("A3", "C3", "2026-11-11T15:00:00+00:00")
        ledger.append(self.path, {"type": "disposition", "at": "2026-11-12T10:00:00+00:00", "appt": "A3",
                                  "qualified": False, "reason": "outside_service_area"})
        self.book("A4", "C4", "2026-11-11T17:00:00+00:00")
        self.book("A5", "C1", "2026-11-20T15:00:00+00:00")
        self.book("A6", "C6", "2026-11-21T15:00:00+00:00", last_purchase="2026-10-15T00:00:00+00:00")
        self.book("A7", "C7", "2026-11-25T15:00:00+00:00")
        ledger.append(self.path, {"type": "disposition", "at": "2026-11-25T17:00:00+00:00", "appt": "A7", "qualified": True})
        self.book("A8", "C2", "2026-11-26T15:00:00+00:00")
        s = self.status("2026-11-26T16:00:00+00:00")
        self.assertEqual(s["A1"][0], "qualified")
        self.assertEqual(s["A2"], ("not_counted", "no_show"))
        self.assertEqual(s["A3"], ("not_counted", "outside_service_area"))
        self.assertEqual(s["A4"], ("qualified", "no dispute inside the window"))
        self.assertEqual(s["A5"], ("not_counted", "duplicate"))
        self.assertEqual(s["A6"], ("not_counted", "existing_customer"))
        self.assertEqual(s["A7"][0], "qualified")
        self.assertEqual(s["A8"][0], "awaiting_window")

    def test_late_dispute_still_counts(self):
        self.book("A1", "C1", "2026-11-10T15:00:00+00:00")
        ledger.append(self.path, {"type": "disposition", "at": "2026-11-20T15:00:00+00:00", "appt": "A1",
                                  "qualified": False, "reason": "fails_criteria"})
        self.assertEqual(self.status("2026-11-21T00:00:00+00:00")["A1"][0], "qualified")

    def test_deposit_draws_to_zero_then_asks_for_a_topup(self):
        for i in range(6):
            self.book(f"A{i}", f"C{i}", f"2026-11-1{i}T15:00:00+00:00")
        out = ledger.settle(self.path, TERMS, "2026-11-25T00:00:00+00:00")
        self.assertEqual(len(out["charged"]), 6)
        self.assertEqual(out["credit_usd"], -100.0)
        self.assertEqual(out["balance_due_usd"], 100.0)
        self.assertTrue(out["topup_needed"])
        again = ledger.settle(self.path, TERMS, "2026-11-26T00:00:00+00:00")
        self.assertEqual(again["charged"], [])

    def test_day_90_review(self):
        self.assertFalse(ledger.review_due(ledger.read(self.path), TERMS, "2027-02-04T00:00:00+00:00"))
        self.assertTrue(ledger.review_due(ledger.read(self.path), TERMS, "2027-02-05T15:00:00+00:00"))
        ledger.append(self.path, {"type": "review", "at": "2027-02-06T00:00:00+00:00", "choice": "commission"})
        self.assertFalse(ledger.review_due(ledger.read(self.path), TERMS, "2027-02-07T00:00:00+00:00"))


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.folder = Path(onboard.onboard(sample(), self.tmp / "clients")["folder"])
        self.stub = self.tmp / "orgo"
        self.stub.write_text(STUB_ORGO)
        self.stub.chmod(self.stub.stat().st_mode | stat.S_IEXEC)
        self.log = self.tmp / "orgo.log"
        os.environ["ORGO_LOG"] = str(self.log)
        os.environ.pop("ORGO_COMPUTERS", None)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def raw(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

    def calls(self):
        """Each orgo call's arguments, without the stub's KEY marker."""
        return [c[:-1] for c in self.raw()]

    def lock(self):
        p = self.tmp / "engine.lock.json"
        p.write_text(json.dumps({"repo": "jbellsolutions/example-engine", "tag": "v0.0.1", "sha256": "0" * 64}))
        return p

    def test_dry_run_touches_nothing(self):
        res = install.run(self.folder, str(self.stub), lock_path=self.lock())
        self.assertEqual(self.calls(), [])
        self.assertIn("waiting_on_person", [r["result"] for r in res])

    def test_without_an_engine_release_it_stops_at_the_engine(self):
        res = install.run(self.folder, str(self.stub), apply=True, yes=True, lock_path=self.tmp / "none.json")
        self.assertEqual(res[-1]["id"], "engine")
        self.assertEqual(res[-1]["result"], "blocked")
        self.assertFalse(any("rcm-engine" in " ".join(c) for c in self.calls()))

    def test_apply_without_yes_only_reads(self):
        install.run(self.folder, str(self.stub), apply=True, lock_path=self.lock())
        verbs = [c[c.index("computers") + 1] if "computers" in c else c[-1] for c in self.calls()]
        self.assertEqual(verbs, ["whoami", "list"])

    def test_apply_with_yes_creates_installs_and_checks(self):
        res = install.run(self.folder, str(self.stub), profile="harbor", apply=True, yes=True, lock_path=self.lock())
        by = {r["id"]: r["result"] for r in res}
        self.assertEqual(by["computer"], "ok")
        self.assertEqual(by["support"], "waiting_on_person")
        self.assertEqual(by["check"], "ok")
        calls = self.calls()
        self.assertTrue(all(c[:2] == ["--profile", "harbor"] for c in calls))
        create = next(c for c in calls if "create" in c)
        self.assertEqual(create[create.index("--ram") + 1], "8")
        engine = next(c for c in calls if "bash" in c and "sha256sum" in c[-1])
        self.assertIn("v0.0.1", engine[-1])

    def test_btg_key_and_workspace_are_reused_and_never_printed(self):
        env = self.tmp / "btg.env.local"
        env.write_text("OPENROUTER_API_KEY=other-secret\nORGO_API_KEY=test-key-not-real\nBOPS_ORGO_WORKSPACE=bops\n")
        res = install.run(self.folder, str(self.stub), apply=True, yes=True, lock_path=self.lock(), btg_env_path=env)
        ids = [r["id"] for r in res]
        self.assertNotIn("btg", ids)
        self.assertIn("btg_attach", ids)
        self.assertTrue(all(c[-1] == "KEY=set" for c in self.raw()))
        calls = self.calls()
        create = next(c for c in calls if "create" in c)
        self.assertEqual(create[create.index("--workspace") + 1], "bops")
        self.assertNotIn("test-key-not-real", json.dumps(res))
        self.assertNotIn("other-secret", json.dumps(calls))

    def test_a_pack_engine_goes_up_in_pieces_checked_by_sha256(self):
        import hashlib
        blob = os.urandom(150_000)
        (self.folder / "deliver" / "engine").mkdir(parents=True, exist_ok=True)
        (self.folder / "deliver" / "engine" / "engine.tar.gz").write_bytes(blob)
        lock = self.tmp / "pack.lock.json"
        lock.write_text(json.dumps({"bundle": "pack", "file": "engine.tar.gz", "version": "t",
                                    "sha256": hashlib.sha256(blob).hexdigest()}))
        res = install.run(self.folder, str(self.stub), apply=True, yes=True, lock_path=lock)
        order = [r["id"] for r in res if r["id"] in ("charters", "engine", "profiles")]
        self.assertEqual(order, ["charters", "engine", "profiles"])
        self.assertEqual({r["id"]: r["result"] for r in res}["engine"], "ok")
        bash = [c[-1] for c in self.calls() if "bash" in c]
        chunks = [c for c in bash if c.startswith("printf %s ")]
        self.assertGreater(len(chunks), 1)
        final = next(c for c in bash if "sha256sum -c" in c and "rcm-engine.tar.gz" in c)
        self.assertIn(hashlib.sha256(blob).hexdigest(), final)
        profiles = next(c for c in bash if "rcm-engine profile" in c)
        self.assertNotIn("rcm-engine profile radar", profiles)
        self.assertIn("radar", [r["id"] for r in res])

    def test_a_tampered_pack_engine_is_refused(self):
        (self.folder / "deliver" / "engine").mkdir(parents=True, exist_ok=True)
        (self.folder / "deliver" / "engine" / "engine.tar.gz").write_bytes(b"not the pinned engine")
        lock = self.tmp / "pack.lock.json"
        lock.write_text(json.dumps({"bundle": "pack", "file": "engine-missing.tar.gz", "sha256": "0" * 64}))
        res = install.run(self.folder, str(self.stub), apply=True, yes=True, lock_path=lock)
        self.assertEqual((res[-1]["id"], res[-1]["result"]), ("engine", "blocked"))

    def test_without_btg_it_asks_for_it_first(self):
        steps = install.plan(self.folder, "orgo")
        self.assertEqual((steps[0]["id"], steps[0]["kind"]), ("btg", "person"))

    def test_an_existing_computer_is_reused(self):
        os.environ["ORGO_COMPUTERS"] = json.dumps([{"name": "Reactivation"}])
        res = install.run(self.folder, str(self.stub), apply=True, yes=True, lock_path=self.lock())
        self.assertEqual({r["id"]: r["result"] for r in res}["computer"], "skipped")
        self.assertFalse(any("create" in c for c in self.calls()))


ENGINE_SRC = Path(os.environ.get("RCM_ENGINE_SRC") or Path.home() / "AI OS Market Share " / "AIOS" / "Our AIOS" / "agents" / "gtm-box")


@unittest.skipUnless((ENGINE_SRC / "build" / "opener").is_dir(), "the CRM team's source isn't on this machine")
class EngineBuildTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_engine", ROOT / "scripts" / "build_engine.py")
        self.be = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.be)

    def test_deterministic_client_clean_and_paused(self):
        import gzip, io as _io, tarfile as _tar
        blob1, _, _ = self.be.build()
        blob2, _, man = self.be.build()
        self.assertEqual(blob1, blob2)
        with _tar.open(fileobj=_io.BytesIO(blob1), mode="r:gz") as tar:
            names = tar.getnames()
            read = lambda n: tar.extractfile(n).read().decode()
            for name in ("opener", "replies", "closer", "deals"):
                self.assertTrue(read(f"engine/profiles/{name}/SOUL.md").startswith("{{AGENT_CHARTER}}"))
                jobs = json.loads(read(f"engine/profiles/{name}/cron/jobs.json"))["jobs"]
                self.assertTrue(all(j.get("enabled") is False for j in jobs), name)
            crm_map = json.loads(read("engine/crm-map.template.json"))
            self.assertEqual((crm_map["location"], crm_map["lanes"], crm_map["templates"]), ("", {}, {}))
            everything = "".join(read(n) for n in names if tar.getmember(n).isfile())
        self.assertNotIn(json.loads((ENGINE_SRC / "crm-map.json").read_text())["location"], everything)
        self.assertIn("engine/install.sh", names)
        self.assertIn("engine/rcm-engine", names)

    def test_render_fills_the_client_charter(self):
        import gzip, io as _io, tarfile as _tar, subprocess
        blob, _, _ = self.be.build()
        tmp = Path(tempfile.mkdtemp())
        try:
            with _tar.open(fileobj=_io.BytesIO(blob), mode="r:gz") as tar:
                tar.extractall(tmp)
            res = onboard.onboard(sample(), tmp / "clients")
            home = tmp / "rcm"
            (home / "charters").mkdir(parents=True)
            shutil.copytree(Path(res["folder"]) / "deliver" / "charters", home / "charters", dirs_exist_ok=True)
            shutil.copy(Path(res["folder"]) / "deliver" / "manifest.json", home / "manifest.json")
            (home / "box").mkdir()
            subprocess.run([sys.executable, str(tmp / "engine" / "render.py"), "--bundle", str(tmp / "engine"),
                            "--manifest", str(home / "manifest.json"), "--out", str(home)], check=True,
                           capture_output=True)
            soul = (home / "build" / "opener" / "SOUL.md").read_text()
            self.assertIn("Project charter: Harbor Test Roofing reactivation", soul)
            self.assertNotIn("{{", soul)
            self.assertEqual(json.loads((home / "box" / "crm-map.json").read_text())["owner_user"], "Dana")
        finally:
            shutil.rmtree(tmp)


class EndToEndTests(unittest.TestCase):
    """Signup, record, install dry run, appointments, statement, day-90: one made-up client."""

    def test_signup_to_statement(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            res = onboard.onboard(sample(), tmp, readout=EXAMPLE / "readout-stub.txt")
            folder = Path(res["folder"])
            plan = install.plan(folder, "orgo")
            self.assertEqual([s["id"] for s in plan[:2]], ["btg", "signed_in"])
            path = folder / "ledger" / "events.jsonl"
            terms = json.loads((folder / "deliver" / "manifest.json").read_text())["rcm"]["terms"]
            for i, (contact, show) in enumerate([("C1", True), ("C2", False), ("C3", True), ("C4", True),
                                                  ("C5", True), ("C6", True), ("C7", True)]):
                slot = f"2026-11-{10 + i}T15:00:00+00:00"
                ledger.append(path, {"type": "booked", "at": "2026-11-09T12:00:00+00:00", "appt": f"A{i}",
                                     "contact": contact, "slot": slot, "evidence": f"cal:A{i}"})
                ledger.append(path, {"type": "held" if show else "no_show", "at": slot, "appt": f"A{i}"})
            ledger.append(path, {"type": "disposition", "at": "2026-11-13T18:00:00+00:00", "appt": "A3",
                                 "qualified": False, "reason": "not_decision_maker"})
            out = ledger.settle(path, terms, "2027-02-06T00:00:00+00:00")
            self.assertEqual(len(out["charged"]), 5)
            self.assertEqual(out["credit_usd"], 0.0)
            self.assertTrue(out["topup_needed"])
            self.assertTrue(out["review_due"])
            text = ledger.statement(path, terms, "2027-02-06T00:00:00+00:00", "Harbor Test Roofing")
            self.assertIn("Top-up needed", text)
            self.assertIn("Day-90 review due", text)
            self.assertIn("not_decision_maker", text)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
