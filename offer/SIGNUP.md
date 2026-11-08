# Signup: in Justin's order, with no person needed

Justin, 2026-11-07: "The first step would be the sales page, and then they'd click on just a quick agreement they would sign... It would be like this page here, where the voice AI would get all the information, and the last step would be the payment."

Live in Stripe test mode at https://reactivation-signup.pages.dev (`web/`, Cloudflare Pages project `reactivation-signup`).

| # | Step | Page | What it writes | State |
|---|---|---|---|---|
| 1 | The offer | `/` | Nothing | Live |
| 2 | A one-page lead generation agreement, signed with a typed full name, an email and a box | `/agreement/`, `POST /api/agreement` | A new Reactivation Signups row: `agreement signed`, with the signature (name, email, time, IP, version) | Live. The text is a stand-in until Justin's own one-pager replaces it |
| 3 | The voice intake: the business, what they sell and where, the CRM, the lists and their text consent, and "just your past leads, or also new people asking?". It tells them what a qualified appointment is; it doesn't ask | `/intake/`, `POST /api/voice` (GPT-Live, `gpt-live-1`), `POST /api/intake`; typed fallback on the same page | The answers on the same row: `intake done` | Typed path live. Voice waits on `OPENAI_API_KEY` in the site's settings |
| 4 | The $500 deposit, last | Stripe Payment Link, carrying the row as `client_reference_id` and the signer's email | Nothing yet | Live in test mode |
| 5 | Back from Stripe | `/thanks/`, `POST /api/paid` | The row becomes `new`, with its Checkout session | Live |
| 6 | The poller, every 15 minutes | `rcm poll --write-builds` | The client record in Client Builds, its pack, a queued install email, its Builds row; `needs price` until Justin sets the client's Price | Live |

**Not asked at signup** (Justin): who takes the appointments, a booking link, Orgo, the model. The booking link and time zone come at the setup call, and the record lists them as a need. The qualified-appointment definition is the standard one in `offer.json`.

**Proven** on 2026-11-07, test mode, on the live site:
- agreement, then answers, then the $500 test deposit;
- `/thanks/` marked the row `new`;
- the poller made "Flow Test Remodeling" in Client Builds and its Builds row, waiting on a price and the setup call.

An earlier test with a test price showed the deposit opening as $500 credit, and the statement.
