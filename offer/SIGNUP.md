# Signup: no person needed, and a call if they want one

Justin: "A person could theoretically sign up without having to talk to anybody. If they do, they talk to us on a readout recording."

## Self-serve

| # | Step | Tool | Lands in |
|---|---|---|---|
| 1 | The signup page explains the offer and links to the deposit | A page on everyoneneedsanaiguy.com, outside the main nav (the main pages carry no prices) | Not published: GO-LIVE 6 |
| 2 | $500 deposit. Accepting the agreement is required, and the card is saved for top-ups | A Stripe Payment Link with terms of service consent and the card saved for later charges | Not created: GO-LIVE 4 |
| 3 | After paying, they land on the intake form | The Payment Link's after-payment redirect | |
| 4 | The intake form: business, what they sell, area, rep, booking link, criteria, lists and consent, CRM, Orgo, model, Lead Radar yes or no | A Notion form feeding a Reactivation Signups database, field names as in `examples/synthetic-client/form-row.json` | Not created: GO-LIVE 5 |
| 5 | The poller matches the paid session to the form row by email | `rcm signup` turns the pair into an intake | Built and tested |
| 6 | The record is made: folder, charters, manifest, ledger opened with the deposit, the Builds row | `rcm onboard` | Built and tested |
| 7 | The install email goes out with their one line | Approved once as a template, then automatic | Template: GO-LIVE 13 |
| 8 | They install from Claude Code, the agents start paused, and they approve the offer and copy | `kit/INSTALL.md`, `rcm install` | Built, dry-run tested. The engine release is M1 |

## With a call

The call books through Cal.com. Read AI records it and delivers it to `Recordings/inbox/`. `cb recordings` routes it to the client's folder, and the Factory's spec pass (no tools, firewalled) turns it into the same intake fields. From there it's step 6. Nothing in `rcm` reads a transcript.

The call agenda is `../onboarding/READOUT-CALL.md`.

## Page copy (draft, unpublished)

> **Pay only for appointments that happen.**
> An AI agent goes through your CRM, finds everyone who asked for a quote or bought once and went quiet, and restarts the conversation one person at a time. When someone's interested, it books them with your team.
> For the first 90 days you pay only for qualified appointments: the person showed up, they're interested, and they fit what you told us you need. Not for leads, and not for no-shows.
> Put $500 down. It's credit toward your appointments.
> The agent runs on your own computer and your own accounts, and you can watch it work.
