"""The install, step by step, against the client's Orgo computer through the `orgo` CLI.

    rcm install <client folder>                 # the plan: every step, who does it, what proves it
    rcm install <client folder> --apply         # run the automatic steps; a step that asks waits for --yes
    rcm install <client folder> --apply --yes   # the client said yes to creating and changing their computer

Kinds: `auto` reads only, and runs on --apply. `asks` changes the client's computer or account, and runs on
--apply --yes, which the kit passes only after the client says yes in the chat. `person` is a click only a
person makes (signing in, inviting support), so the kit opens the screen and waits. `blocked` can't run yet,
and says why.

The engine is pinned in kit/engine.lock.json (repo, tag, sha256) and installed from that release. The kit
never carries a copy of the engine.
"""

import base64
import io
import json
import subprocess
import tarfile
from pathlib import Path

from .onboard import ENGINE_LOCK

COMPUTER = {"ram": "8", "cpu": "2", "disk": "40"}
SUPPORT_EMAIL = "support@usingaitoscale.com"


def engine_lock(path=ENGINE_LOCK):
    p = Path(path)
    lock = json.loads(p.read_text()) if p.exists() else {}
    return lock if lock.get("repo") and lock.get("tag") and lock.get("sha256") else None


def charters_payload(folder):
    """The rendered charters as one base64 tar, so they reach the computer in a single command."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        tar.add(Path(folder) / "deliver" / "charters", arcname="charters")
        tar.add(Path(folder) / "deliver" / "manifest.json", arcname="manifest.json")
    return base64.b64encode(buf.getvalue()).decode()


def plan(folder, orgo="orgo", profile=None, lock_path=ENGINE_LOCK, support_email=SUPPORT_EMAIL):
    folder = Path(folder)
    m = json.loads((folder / "deliver" / "manifest.json").read_text())
    name = m["orgo"]["computer_name"]
    base = [orgo] + (["--profile", profile] if profile else [])
    profiles = m["rcm"]["profiles"]
    lock = engine_lock(lock_path)
    steps = [
        {"id": "signed_in", "kind": "auto", "who": "kit", "cmd": base + ["--json", "whoami"],
         "proof": "Orgo answers with the client's account",
         "if_fails": "the client signs in: `orgo login` opens the browser (or buys a computer in Better than GrokBot)"},
        {"id": "computer_exists", "kind": "auto", "who": "kit", "cmd": base + ["--json", "computers", "list"],
         "proof": f"a computer named {name!r} is listed"},
        {"id": "computer", "kind": "asks", "who": "kit, on the client's yes",
         "cmd": base + ["computers", "create", "--name", name, "--ram", COMPUTER["ram"],
                        "--cpu", COMPUTER["cpu"], "--disk", COMPUTER["disk"]],
         "proof": "Starter's one always-on Medium: 8 GB, 2 vCPU, 40 GB, on the client's own plan",
         "skip_if": "computer_exists"},
    ]
    if lock:
        script = (f"set -e; curl -fsSL https://github.com/{lock['repo']}/releases/download/{lock['tag']}/install.sh"
                  f" -o /root/rcm-engine.sh && echo '{lock['sha256']}  /root/rcm-engine.sh' | sha256sum -c -"
                  f" && bash /root/rcm-engine.sh --client {m['client']}")
        steps.append({"id": "engine", "kind": "asks", "who": "kit, on the client's yes",
                      "cmd": base + ["computers", "bash", name, "-c", script],
                      "proof": "the release's own installer passes its checksum and its check"})
    else:
        steps.append({"id": "engine", "kind": "blocked", "who": "Justin",
                      "cmd": None, "proof": "an engine release is pinned in kit/engine.lock.json",
                      "if_fails": "no engine release yet: the leads build of the affiliate manager (plan M1)"})
    payload = charters_payload(folder)
    steps += [
        {"id": "charters", "kind": "asks", "who": "kit, on the client's yes",
         "cmd": base + ["computers", "bash", name, "-c",
                        f"mkdir -p /root/.rcm && echo {payload} | base64 -d | tar -xz -C /root/.rcm"],
         "proof": "/root/.rcm/charters holds the project charter, the agent charter and each profile's"},
        {"id": "profiles", "kind": "asks", "who": "kit, on the client's yes",
         "cmd": base + ["computers", "bash", name, "-c",
                        " && ".join(f"rcm-engine profile {p} --charter /root/.rcm/charters/profiles/{p}/CHARTER.md --paused"
                                    for p in profiles)],
         "proof": f"{len(profiles)} profiles installed, every scheduled job paused: {', '.join(profiles)}"},
        {"id": "support", "kind": "person", "who": "the client",
         "cmd": None, "proof": f"{support_email} is a Full access member of the client's Orgo workspace",
         "how": f"Orgo, Settings, Members, Invite people: {support_email}, Full access. Starter allows one person."},
        {"id": "crm_sign_in", "kind": "person", "who": "the client",
         "cmd": base + ["computers", "view", name],
         "proof": "the CRM is signed in on the computer's browser; the agents never see the password"},
        {"id": "check", "kind": "asks", "who": "kit",
         "cmd": base + ["computers", "bash", name, "-c", f"rcm-engine check --client {m['client']}"],
         "proof": "every line passes: memory, profiles, CRM token without send rights, gate, consent, STOP"},
    ]
    return steps


def run(folder, orgo="orgo", profile=None, apply=False, yes=False, runner=subprocess.run,
        lock_path=ENGINE_LOCK):
    """Walk the plan. Returns one result per step; never runs an `asks` step without yes."""
    results, seen = [], {}
    for s in plan(folder, orgo, profile, lock_path):
        if s.get("skip_if") and seen.get(s["skip_if"]):
            results.append({**s, "result": "skipped", "note": "already there"})
            continue
        if s["kind"] == "blocked":
            results.append({**s, "result": "blocked", "note": s["if_fails"]})
            break
        if s["kind"] == "person":
            results.append({**s, "result": "waiting_on_person", "note": s.get("how", s["proof"])})
            continue
        if not apply or (s["kind"] == "asks" and not yes):
            results.append({**s, "result": "planned", "note": "dry run" if not apply else "waits for the client's yes"})
            continue
        p = runner(s["cmd"], capture_output=True, text=True)
        ok = p.returncode == 0
        if s["id"] == "computer_exists":
            name = json.loads((Path(folder) / "deliver" / "manifest.json").read_text())["orgo"]["computer_name"]
            ok = ok and name in (p.stdout or "")
            seen[s["id"]] = ok
            results.append({**s, "result": "ok" if ok else "absent", "note": ""})
            continue
        seen[s["id"]] = ok
        results.append({**s, "result": "ok" if ok else "failed", "note": (p.stderr or "")[-300:]})
        if not ok:
            break
    return results
