# Install: the steps the client's Claude Code follows

The client pastes their one line from `deliver/INSTALL.md`. Claude Code reads this file and does the work, checking each step before the next. Rules for the installing agent:

- **Never type a password, MFA code or key.** Keys go in at a hidden prompt (`read -s`) and straight into the computer's environment, never into the chat or a file in this repo.
- **Ask before anything that changes the client's computer or spends their money**, then pass `--yes`.
- **Report each step as done, waiting on them, or blocked, with the reason.**

## 0. The client's pack

Their pack is the zip attached to their install email (`rcm pack`): their charters, their manifest and this install note, and nothing else from their record. Unzip it, then check that `deliver/manifest.json` is there and names their business.

## 1. Better than GrokBot: the window, and where the computer comes from (default)

Install Better than GrokBot from https://github.com/jbellsolutions/better-than-grokbot (its INSTALL.md). It needs the client's Orgo key in its `.env.local`:
- **Already on Orgo:** they make a key at orgo.ai, API keys.
- **New to Orgo:** they sign up there, pick Starter ($29 a month for one always-on computer, on their own card), then make the key.

Better than GrokBot's own docs say its install hasn't been proven on a client's Mac yet. If it fails, or the client says no, skip to the Orgo CLI: `orgo login`.

## 2. The plan

```bash
bin/rcm install <client folder> --btg-env <Better than GrokBot's .env.local>
```

That prints the plan. `--btg-env` reuses the Orgo key and workspace Better than GrokBot already has. The kit reads only those two values and never prints them. The computer is then bought in the same account and workspace, so it shows up in Better than GrokBot.

## 3. Their computer, the engine, the charters, the agents

Ask for a yes, then:

```bash
bin/rcm install <client folder> --btg-env <Better than GrokBot's .env.local> --apply --yes
```

This does four things:
- creates the computer, or reuses one named Reactivation;
- installs the pinned engine release from `kit/engine.lock.json`;
- copies the charters;
- installs one profile per agent, with every scheduled job paused.

**The model key** goes in at the engine's hidden prompt.

**If the engine step says blocked,** stop and tell them: their record is ready, and the agents install when the release is published.

## 4. Support access

They invite AI Guy support:
- Orgo, Settings, Members, Invite people: `support@usingaitoscale.com`, Full access.
- Starter allows one person, so this uses it.
- They can remove it any time.

## 5. Their CRM

Open the computer's screen:

```bash
orgo computers view Reactivation
```

They sign in to their CRM in the browser there, MFA included. For GoHighLevel, Attio or Zoho, the engine then asks for a token without send rights, at a hidden prompt.

## 6. Show it in Better than GrokBot

In Better than GrokBot: the main agent, Details, Orgo computer, choose **Reactivation**, then **Use this computer**. Now they can watch every screen, and take control if they want.

## 7. The check

The last step of `rcm install` runs the engine's check. Every line passes, or names its fix.

## 8. Approve and go

The agents draft the offer and the first messages. The client approves them once, and the first wave goes out.

End with: "You'll get a report at the end of each day, and a statement each week."
