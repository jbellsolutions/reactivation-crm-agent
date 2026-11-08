# Reactivation CRM Agent

A pay-per-qualified-appointment offer with an AI-native, hands-off delivery line. A client puts $500 down. A reactivation CRM agent installs on their own Orgo computer, restarts conversations with everyone in their CRM who went quiet, and books qualified appointments. They pay only for those, for the first 90 days.

Justin, 2026-11-07: "For the most part, though, we want to do it as a reactivation CRM agent... it should get installed automatically."

## The line

```
web/: sales page -> signed agreement -> voice intake (GPT-Live) -> $500 deposit, last -> a Signups row in Notion
  -> rcm poll          every new paid row, on a schedule: the rest of this line, no person
  -> rcm signup        the paid session and the form become one intake
  -> rcm onboard       the client's record in the folder system: charters, manifest, ledger, Builds row
  -> rcm pack          the client's own pack for the install email
  -> kit/INSTALL.md    the client's Claude Code: Orgo, the engine, charters, agents, support access, CRM sign-in
  -> the agents        reactivation, reply, sales, deal (+ radar)
  -> rcm collect       their ledger read back over Orgo
  -> rcm ledger        settle, statement, top-up, day-90 review
```

## Where things are

| | |
|---|---|
| `offer/` | The offer, the qualified-appointment rule, the agreement template, signup |
| `onboarding/` | The stage contracts and the readout-call agenda |
| `kit/` | The install steps, the charter templates, the engine contract and pin |
| `tracking/` | How results reach us and become statements |
| `gtm/HANDOFF.md` | The offer for the go-to-market sessions |
| `GO-LIVE.md` | Every gated step, who and what it costs |
| `rcm/` | The code (Python 3.9+, standard library only) |
| `web/` | The signup page, the intake page and `POST /api/intake` (a Cloudflare Pages site, not deployed) |
| `scripts/golive.py` | The Stripe deposit link and the Notion Signups database: printed first, made only on `--apply` |

## Use it

```bash
bin/rcm signup --session examples/synthetic-client/checkout-session.json --form examples/synthetic-client/form-row.json --out /tmp/intake.json
```

```bash
bin/rcm onboard /tmp/intake.json --clients /tmp/clients --readout examples/synthetic-client/readout-stub.txt
```

```bash
bin/rcm install "/tmp/clients/Harbor Test Roofing"
```

Test it:

```bash
python3 -m unittest discover tests
```

```bash
cd web && node --test tests/*.test.js
```

## State

Built and tested offline:
- the signup site and its endpoint;
- the poller, against a stand-in Notion and Stripe;
- onboarding;
- the Better than GrokBot install plan, against a stand-in `orgo`;
- the ledger and statements.

Not live: everything in `GO-LIVE.md`, the engine release above all.
