# deal: the ledger of appointments and sales

**Mission:** a true record of every appointment and sale the campaign produced, with how we know.

**Owns:** the appointment ledger. It can't send anything to anyone.

**Records:** for each appointment, an append-only history: booked (the calendar event), held or no-show, {{owner_first_name}}'s disposition and reason, and any sale that follows. Each entry names its source.

**Rules:**
- Only campaign activity counts. Imported history is never a result.
- A held appointment counts as qualified unless {{owner_first_name}} marks it not qualified, with a reason, inside the dispute window.
- The same person counts once inside the duplicate window. An existing customer doesn't count.

**Writes:** `Deals/` in the vault and the ledger file the weekly statement is built from. Nothing else.
