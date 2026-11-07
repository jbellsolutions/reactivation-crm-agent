# Onboarding: AI-native, from signup to a live campaign

One client is one record in the folder system: `Client Builds/<Business>/`, made by `rcm onboard`. Every stage below has one contract and ends in exactly one check. No stage needs a person except where the check says so.

| # | Stage | Input | Do | Output | Check |
|---|---|---|---|---|---|
| 1 | Signup | A paid deposit, or a booked call | Stripe Payment Link; or Cal.com plus Read AI | A paid Checkout session, or a recording in `Recordings/inbox/` | The session is paid at $500 with the agreement accepted (`rcm signup`) |
| 2 | Intake | The session plus the form row, always; a readout call adds context through the Factory | `rcm poll` runs `rcm signup` | `intake.json` | `intake.validate` returns nothing |
| 3 | Record | `intake.json` | `rcm onboard` | The client folder, charters, manifest, ledger, Builds row, `NEEDS.md` | No template placeholder is left; the manifest parses |
| 4 | Install line | The record | The approved install email | The client has their one line | The email went through the approved template |
| 5 | Install | The client's Claude Code, their Orgo account | `kit/INSTALL.md`, `rcm install --apply --yes` | A computer with the engine, charters and profiles, all paused | Every step is `ok` or waits on a person by design |
| 6 | People | The client | Signs in to the CRM on the computer's screen; invites support to the Orgo workspace | Logged-in browser; support is a member | The engine's check passes the CRM and support lines |
| 7 | Approve | Drafts of the offer and the first messages | The client approves once | Copy approved | Approval recorded on the gate |
| 8 | Live | Approved copy | Agents run in waves | Replies, bookings, appointments | The end-of-day report arrives |
| 9 | Statement | The ledger | `rcm ledger settle` and `statement`, weekly | Charges frozen, the statement, any top-up request | Every line traces to its events |
| 10 | Day 90 | The ledger | Review call: commission, or stay per appointment | A `review` event | `review_due` is false |

**Where it shows up.**
- Each record is in `Client Builds/` (the `aios-workspace` repo).
- Its Builds row goes to Notion's Command Center through the Factory's write-back (`Source ID` is `rcm:<slug>`). The roster sync links it to the Clients row.
- We never write a client's Notion page directly.

**Who's in the loop.**
- Justin takes the readout calls and the gated go-live steps.
- The client signs in, approves copy and marks appointments.
- Everything else is the system.
