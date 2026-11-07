# Go-live: what turns this on, who, and what it costs

Everything below is gated: money, publishing, a remote write, or a decision only Justin makes. The code and the tests don't need any of it.

| # | Step | Who | Cost | Unblocks |
|---|---|---|---|---|
| 1 | Set the price per qualified appointment. Proposed: $100, so the deposit covers five | Justin | None | Terms, statements, the agreement |
| 2 | Set the commission rate after day 90, and what happens to unused credit | Justin | None | Agreement section 5 |
| 3 | A lawyer reads the agreement's consent, indemnity and qualified-appointment clauses (or Justin decides not to) | Justin | A lawyer's fee | Publishing the agreement |
| 4 | The Stripe Payment Link: a $500 deposit, terms of service consent required and pointing at the published agreement, the card saved for top-ups, an after-payment redirect to the intake form | Justin's yes, then Claude | Stripe's fee on each charge, from the deposit | Self-serve signup |
| 5 | The intake form: a Notion form feeding a Reactivation Signups database, with the field names in `examples/synthetic-client/form-row.json`. The Notion agent in `~/Notion Interface` owns Command Center layout | Justin's yes | None | Self-serve signup |
| 6 | The signup page on everyoneneedsanaiguy.com, outside the main nav (copy in `offer/SIGNUP.md`) | Justin's yes to deploy | None | Self-serve signup |
| 7 | The poller: a restricted Stripe key that reads Checkout sessions, and the Notion token, each added with `add-secret`. It runs `rcm signup` and `rcm onboard` on each new paid pair. It belongs on the Factory's box tick or the Our AIOS daily pass | Justin adds the keys | None | Signup to a record with no person |
| 8 | The engine release: the leads build of the affiliate manager, pinned in `kit/engine.lock.json` | Justin points to its source (plan M1); the Beta session owns that repo | None | The install past its engine step |
| 9 | A support login: `support@usingaitoscale.com` as a mailbox and a free Orgo account, to accept client workspace invites | Justin (creating accounts is his) | None | Support access and `rcm collect` |
| 10 | The Factory: a `reactivation` platform in `cb`, and `reactivation-crm-agent` in Notion's product catalog | The Factory session, then the Notion sync | None | Builds rows that link; readout calls to intake |
| 11 | One shared send gate for all clients (`deploy/gate/` from the affiliate manager, made multi-tenant) | Justin's yes to deploy on Railway | A small fixed monthly cost, not per client | Approved sends |
| 12 | Better than GrokBot: read its FSL-1.1 licence for use inside a paid offer | Justin | None | Offering it in the install |
| 13 | The install email template, approved once | Justin | None | Step 4 of onboarding without a person |
| 14 | The public name, through the Offer session | Justin | None | Page and outreach copy |
| 15 | How clients reach this kit: make the repo public (only Justin can say "public"), or invite each client through a GitHub organization with Read access | Justin | None | Clients' Claude Code can read `kit/INSTALL.md` |

## Per client, after go-live: all on the client's accounts

| | Client pays | We pay |
|---|---|---|
| Orgo computer | $29 a month on their Starter plan, or our Orgo payment link | Nothing |
| Model | Their OpenRouter key, or Orgo AI at cost | Nothing |
| Texting and email | Their CRM | Nothing |
| A signup from the form | Nothing | Nothing |
| A signup from a readout call | Nothing | The Factory's spec pass, inside its per-stage cap |
