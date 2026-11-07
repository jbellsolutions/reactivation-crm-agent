# Signup: no person needed, and a call if they want one

Justin: "A person could theoretically sign up without having to talk to anybody. If they do, they talk to us on a readout recording."

## Self-serve

| # | Step | Tool | Lands in |
|---|---|---|---|
| 1 | The signup page explains the offer and links to the deposit | `web/public/index.html`, its own small Cloudflare Pages site | Built, checked in a browser. Not deployed: GO-LIVE 6 |
| 2 | $500 deposit. Accepting the agreement is required, and the card is saved for top-ups | A Stripe Payment Link, made by `scripts/golive.py stripe` | Script built and dry-run. Not created: GO-LIVE 4 |
| 3 | After paying, they land on the intake page with their session id | The link's redirect to `/intake/?session_id=...` | Built |
| 4 | The intake form: business, what they sell, area, rep, booking link, criteria, lists and consent, CRM, Orgo, model, Lead Radar yes or no | `web/public/intake/`, posting to `POST /api/intake`. That endpoint checks the paid session with Stripe and writes one row to the Reactivation Signups data source in Notion | Built, 6 Node tests. The Signups database: `scripts/golive.py notion`, GO-LIVE 5 |
| 5 | The poller reads new Signups rows and their Stripe sessions | `rcm poll` | Built, tested against a stand-in Notion and Stripe |
| 6 | The record is made: folder, charters, manifest, ledger opened with the deposit, the pack, the Builds row in the Factory's live options | `rcm signup`, `rcm onboard`, `rcm pack`, `rcm poll --write-builds` | Built and tested |
| 7 | The install email, with their pack attached, is queued for the guarded sender | `factory/outbox/install-email.json` | Built. The template is approved once: GO-LIVE 13 |
| 8 | They install from Claude Code, the agents start paused, and they approve the offer and copy | `kit/INSTALL.md`, `rcm install --btg-env` | Built, tested against a stand-in `orgo`. The engine release is M1 |

## With a call

They still pay the deposit and fill in the intake form: their email and booking link have to come from the form, because the Factory's spec pass keeps emails and phone numbers private (its note of 2026-11-07). The call books through Cal.com, and Read AI records it and delivers it to `Recordings/inbox/`. `cb recordings` files it in the client's folder, where it adds context to the build. Nothing in `rcm` reads a transcript.

The call agenda is `../onboarding/READOUT-CALL.md`.

## Page copy (draft, unpublished)

> **Pay only for appointments that happen.**
> An AI agent goes through your CRM, finds everyone who asked for a quote or bought once and went quiet, and restarts the conversation one person at a time. When someone's interested, it books them with your team.
> For the first 90 days you pay only for qualified appointments: the person showed up, they're interested, and they fit what you told us you need. Not for leads, and not for no-shows.
> Put $500 down. It's credit toward your appointments.
> The agent runs on your own computer and your own accounts, and you can watch it work.
