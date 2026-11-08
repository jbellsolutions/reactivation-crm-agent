# Go-live: what's on, what's left, and who

Justin's answers of 2026-11-07:
- **Price:** custom per person and niche.
- **Go-live writes:** all four approved (the Notion database, the Stripe link, deploying the site, the poller and its schedule).
- **Engine:** the CRM team already built for this; no client's repo or computer touched.
- **Kit:** public.

| # | Step | State | Who | Cost |
|---|---|---|---|---|
| 1 | Price per qualified appointment | **Custom per client.** Justin fills Price in the client's Signups row; until then the record waits as `needs price` and the deposit isn't opened | Justin, per client | None |
| 2 | Commission rate after day 90, and unused credit | Open | Justin | None |
| 3 | A lawyer's read of the agreement (`offer/AGREEMENT.md`, published at `/terms/`) | Open | Justin | A lawyer's fee |
| 4 | The Stripe deposit link | **Live in test mode**: $500, paid last, back to `/thanks/`. For live: a live link (`scripts/golive.py stripe --apply` with live keys) and a restricted live read key in place of the test secret | Justin's live keys | Stripe's fee per charge |
| 5 | The Reactivation Signups database | **Done**, with statuses `agreement signed`, `intake done`, `new`, `needs price`, `onboarded`, `needs fix` and the signature field | | None |
| 6 | The signup site | **Live**: https://reactivation-signup.pages.dev (sales, agreement, intake, thanks, terms) | | Free tier |
| 6b | The voice (GPT-Live, `gpt-live-1`) | Built and tested; waits on `OPENAI_API_KEY` in the site's settings. Until then the typed fallback shows | Justin adds the key with `add-secret OPENAI_API_KEY` | OpenAI per second of voice |
| 6c | The agreement | **Done**: adapted from Justin's own 2020 pay-per-appointment agreement (`offer/AGREEMENT.md`, live at `/agreement/` and `/terms/`). Open: the courts for disputes and the provider's legal name | Justin | None |
| 7 | The poller | **Live**: every 15 minutes (launchd `com.usingaitoscale.rcm-poll`) | | None |
| 8 | The engine: the CRM team (opener, replies, closer, deals), packaged by `scripts/build_engine.py`, pinned in `kit/engine.lock.json`, carried in each client's pack | **Built and tested offline.** Not yet run on a client's computer | The first client's install proves it | None |
| 9 | A support login: `support@usingaitoscale.com` and a free Orgo account, to accept client workspace invites | Open | Justin (creating accounts is his) | None |
| 10 | `reactivation-crm-agent` in the Products catalog (`products/catalog.json` in client-build-system, which the Notion sync reads) | **Done.** In the catalog at `12f1968` (front door, price unset); the Notion Products sync carries it | | None |
| 11 | Sending: drafts go through the guarded sender, as the CRM team's do | Already deployed (test mode) | Justin approves each draft type once | Fixed, not per client |
| 12 | Better than GrokBot's FSL-1.1 licence, for use inside a paid offer | Open | Justin | None |
| 13 | Lead Radar for clients who choose it | **Wired**: the install's `radar` step runs Lead Radar's own installer on the same computer once `kit/radar.lock.json` names a release. Lead Radar is still being built in `jbellsolutions/lead-radar-agent`, which is private | Its sessions finish; Justin says it can be public; the lock gets its tag | Their Treg, OpenRouter and Orgo |
| 13 | The install email template, approved once | Open | Justin | None |
| 14 | The public name | Open, through the Offer session | Justin | None |
| 15 | The kit public | **Approved** | | None |

## The keys, once, from this folder

```bash
cd ~/REPOS/reactivation-crm-agent
```

```bash
add-secret STRIPE_SECRET_KEY
```

```bash
add-secret STRIPE_READ_KEY
```

```bash
add-secret NOTION_TOKEN
```

```bash
add-secret CLOUDFLARE_API_TOKEN
```

```bash
add-secret CLOUDFLARE_ACCOUNT_ID
```

Then the rest is one command (it stops at the first step that can't run, and says why):

```bash
bash scripts/go-live.sh
```

## Per client, after go-live: all on the client's accounts

| | Client pays | We pay |
|---|---|---|
| Orgo computer | $29 a month on their Starter plan, bought through Better than GrokBot or Orgo | Nothing |
| Model | Their own key, behind the engine's daily spend guard | Nothing |
| Texting and email | Their CRM | Nothing |
| The signup site and poller | Nothing | Nothing on the free tier |
