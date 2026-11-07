# Tracking: how we see results without being in the room

Justin: "We're able to track the results because it's all done by our CRM agent, who can see what they're doing."

1. **On the client's computer**, the deal agent writes every appointment event to `/root/.rcm/ledger/events.jsonl`, with its evidence.
2. **We read it.** Support is a member of the client's Orgo workspace (or holds the scoped key, on an Orgo Invoicing account). `rcm collect <client folder>` copies the ledger into the client's record over Orgo's API. Nothing on the client's computer needs to reach us, and no service of ours has to run for it.
3. **We bill from it.** `rcm ledger <folder> settle` freezes each new charge. `statement` writes the week's statement with every line's reason. A top-up request and the day-90 review come from the same file.
4. **It shows up for Justin.** The weekly scorecard (sent, replied, booked, held, qualified, charged, credit left) goes to the client's Builds row through the Factory's write-back. Our CRM agent carries it on the client's contact in our CRM.

**Unverified:** whether our Orgo API key sees a client's computers once we're a member of their workspace. If it doesn't, `collect` uses a key scoped to that workspace that the client grants at install. On an Invoicing account we hold the scoped key from the start.
