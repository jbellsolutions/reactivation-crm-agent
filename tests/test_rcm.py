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

from rcm import install, intake, ledger, offer, onboard, signup  # noqa: E402

EXAMPLE = ROOT / "examples" / "synthetic-client"
TERMS = {"price_usd": 100.0, "deposit_usd": 500.0, "intro_days": 90, "dispute_hours": 72,
         "duplicate_days": 90, "existing_customer_days": 60}

STUB_ORGO = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
with open(os.environ["ORGO_LOG"], "a") as f:
    f.write(json.dumps(args) + "\\n")
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

    def calls(self):
        return [json.loads(l) for l in self.log.read_text().splitlines()] if self.log.exists() else []

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
        self.assertFalse(any("bash" in c for c in self.calls()))

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

    def test_an_existing_computer_is_reused(self):
        os.environ["ORGO_COMPUTERS"] = json.dumps([{"name": "Reactivation"}])
        res = install.run(self.folder, str(self.stub), apply=True, yes=True, lock_path=self.lock())
        self.assertEqual({r["id"]: r["result"] for r in res}["computer"], "skipped")
        self.assertFalse(any("create" in c for c in self.calls()))


class EndToEndTests(unittest.TestCase):
    """Signup, record, install dry run, appointments, statement, day-90: one made-up client."""

    def test_signup_to_statement(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            res = onboard.onboard(sample(), tmp, readout=EXAMPLE / "readout-stub.txt")
            folder = Path(res["folder"])
            plan = install.plan(folder, "orgo")
            self.assertEqual(plan[0]["id"], "signed_in")
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
