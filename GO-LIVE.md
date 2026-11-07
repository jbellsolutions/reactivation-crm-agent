# Go-live: what turns this on, who, and what it costs

Everything below is gated: money, publishing, a remote write, or a decision only Justin makes. The code is built and tested without any of it. Each step names its exact command.

| # | Step | Who | Cost | Command or place |
|---|---|---|---|---|
| 1 | The price per qualified appointment. Proposed: $100, so the deposit covers five | Justin | None | `offer/offer.json` `price_per_qualified_appointment_usd` |
| 2 | The commission rate after day 90, and what happens to unused credit | Justin | None | `offer.json`, then agreement section 5 |
| 3 | A lawyer reads the agreement's consent, indemnity and qualified-appointment clauses (or Justin decides not to) | Justin | A lawyer's fee | `offer/AGREEMENT.md`; it has to be live at a public URL for step 4 |
| 4 | The Stripe deposit link. Stripe needs a terms URL in its public details first | Justin's yes | Stripe's fee on each charge, from the deposit | `python3 scripts/golive.py stripe --signup-host <host> --apply` (STRIPE_SECRET_KEY), then put the URL in `web/public/config.js` |
| 5 | The Reactivation Signups database in Notion | Justin's yes | None | `python3 scripts/golive.py notion --parent-page <Command Center page> --apply` (NOTION_TOKEN) |
| 6 | Deploy the signup site, with three settings | Justin's yes to deploy | None on Cloudflare's free tier | `cd web && npx wrangler pages deploy public --project-name reactivation-signup`. Settings: STRIPE_READ_KEY, NOTION_TOKEN, RCM_SIGNUPS_DS |
| 7 | The poller's keys, then its schedule (the Factory's box tick or the Our AIOS daily pass) | Justin adds the keys with `add-secret` | None | `.env.local`: NOTION_TOKEN, STRIPE_READ_KEY, RCM_SIGNUPS_DS, RCM_CLIENTS_ROOT. Run `bin/rcm poll --write-builds` |
| 8 | The engine release: export the affiliate manager into the private `affiliate-os` (decided 10-20), clear the 7FF-specific code the export script lists, add the leads pack and `rcm-engine`, then tag and pin it | Justin's go-ahead and his read of 7FF's NDA | None | `scripts/export_affiliate_os.py` in `funding-affiliate-manager`; then `kit/engine.lock.json` |
| 9 | A support login: `support@usingaitoscale.com` as a mailbox and a free Orgo account, to accept client workspace invites | Justin (creating accounts is his) | None | |
| 10 | Builds rows that link: `reactivation-crm-agent` in Notion's Products catalog | Justin's yes (a Notion write); the Factory has a proposed card for the rest | None | The row already uses Builds' live options: no Stage, Status new or paused |
| 11 | One shared send gate for all clients (`deploy/gate/` from the affiliate manager, made multi-tenant) | Justin's yes to deploy on Railway | A small fixed monthly cost, not per client | |
| 12 | Read Better than GrokBot's FSL-1.1 licence for use inside a paid offer | Justin | None | |
| 13 | The install email template, approved once | Justin | None | `factory/outbox/install-email.json` in any record |
| 14 | The public name, through the Offer session | Justin | None | |
| 15 | How clients reach this kit: make the repo public (only Justin can say "public"; it holds no client data), or invite each client through a GitHub organization with Read | Justin | None | |

## Per client, after go-live: all on the client's accounts

| | Client pays | We pay |
|---|---|---|
| Orgo computer | $29 a month on their Starter plan, bought through Better than GrokBot or Orgo | Nothing |
| Model | Their OpenRouter key, or Orgo AI at cost | Nothing |
| Texting and email | Their CRM | Nothing |
| The signup site and poller | Nothing | Nothing on the free tier |
| A readout call's context | Nothing | The Factory's capped pass |
