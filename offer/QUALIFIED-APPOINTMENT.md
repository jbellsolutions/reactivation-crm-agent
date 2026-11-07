# What a qualified appointment is

Justin: "You talk to somebody who says they're interested, not just a lead that came through. You actually sit down and talk with somebody who says they're interested and wants to do some business."

`rcm/ledger.py` applies these rules in code. The numbers below are `offer.json` defaults; a client's agreement can set its own.

## It counts when all of these hold

1. **The agents worked the contact.** They're in the campaign, and the conversation is in the agents' thread.
2. **They booked through the agent's link.** The calendar event is the evidence.
3. **It was held.** The client's rep sat down with them: the meeting happened.
4. **They're interested, and fit.** They said they want to do business, and they meet the client's criteria from the intake (for example "owns the home", "inside the service area").

## It doesn't count when

- **No-show.** The agents rebook them. If the rebooked appointment is held, that one can count.
- **The client marks it not qualified, with a reason, inside the dispute window** (72 hours after it's held). The reasons: outside the service area, not the decision maker, fails the criteria, wrong number or spam.
- **Duplicate.** The same person already counted inside the duplicate window (90 days).
- **Existing customer.** They bought inside the existing-customer window (60 days) before the appointment.

## Silence counts as yes

A held appointment with no mark inside the dispute window counts as qualified. A mark after the window closes doesn't change it. Justin can adjust a charge by hand, and the ledger records that too.

## The evidence for each one

The deal agent keeps an append-only history per appointment: the booking (calendar event), held or no-show, the client's mark and reason, and any sale after it. Every statement line traces back to those events, and a charge, once made, is never rewritten.
