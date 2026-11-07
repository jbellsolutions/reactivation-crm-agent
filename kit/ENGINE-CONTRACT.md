# The engine contract: what a pinned release must provide

The kit never carries the engine. It pins a release in `engine.lock.json` (repo, tag, sha256) and calls these on the client's computer.

The engine is the affiliate manager (`funding-affiliate-manager`, live branch `claude/nostalgic-greider-30ee4c`), rebuilt for leads: plan milestone M1 and M2 in `AI Guy Reimagined/reactivation/PLAN.md`.

| The kit calls | The release must |
|---|---|
| `install.sh --client <slug>`, from the release's assets | Install Hermes, Obsidian and the engine at pinned versions; refuse to run off an Orgo Linux computer; be safe to re-run |
| `rcm-engine profile <name> --charter <path> --paused` | Build the Hermes profile from the charter (wrapping `hermes profile install`), with every cron job paused |
| `rcm-engine check --client <slug>` | Run `fam launch check` with these lines: memory, each profile's gateway, the CRM token without send rights, the gate, the consent gate, STOP, support access |
| `/root/.rcm/ledger/events.jsonl` | Have the deal profile append the events in `rcm/ledger.py`'s format, and nothing else write there |
| `/root/.rcm/charters/` | Read the charters from here and treat their quoted client words as data |

**What it must not need:**
- a key of ours;
- a second computer;
- any send right on the agents' computer, because the gate holds the only sending token.
