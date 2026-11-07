# The engine contract: what a pinned release must provide

The kit pins the engine in `engine.lock.json` (its sha256) and calls these on the client's computer.

The engine is the CRM team built for this (Justin, 2026-11-07): `opener` restarts conversations, `replies` answers every reply, `closer` moves the pipeline, and `deals` keeps the ledger. `scripts/build_engine.py` packages it from its source with the client's charters in place of its own, and pins the tarball's sha256. The tarball isn't in this repo: it travels only in each paying client's pack.

The kit's names map to the engine's: reactivation is `opener`, reply is `replies`, sales is `closer`, deal is `deals`. Lead Radar isn't in the engine yet.

| The kit calls | The engine does |
|---|---|
| `install.sh --client <slug>`, from the client's pack | Installs Hermes at a pinned commit if it's missing, the CRM team's box scripts and the spend guard, and renders the four profiles with the client's charters. Refuses to run off an Orgo Linux computer; safe to re-run |
| `rcm-engine profile <name> --charter <path> --paused` | Installs that profile with `hermes profile install`, puts the kit's charter in it, every job paused |
| `rcm-engine keys` | Asks for the CRM key, the location and the model key at hidden prompts; the model key goes only to the spend guard |
| `rcm-engine check --client <slug>` | Pass or fail per line: engine, each profile, its keys, the CRM location, drafts only, the manifest, STOP |
| `/root/.rcm/ledger/events.jsonl` | The deal profile appends the events in `rcm/ledger.py`'s format, and nothing else writes there |
| `/root/.rcm/charters/` | Read as the client's charters; their quoted client words are data |
