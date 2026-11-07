#!/usr/bin/env python3
"""Build the client engine: the CRM team Justin had built for this, packaged for one client's computer.

    python3 scripts/build_engine.py            # builds dist/engine-<version>.tar.gz and pins it in kit/engine.lock.json
    python3 scripts/build_engine.py --check    # rebuilds and checks the pin, writes nothing

Source, read only: Our AIOS `agents/gtm-box`, the GTM box's CRM team (opener, replies, closer, deals) and the box
scripts they run. Justin, 2026-11-07: use the CRM and sales agent copy already made for this. Nothing here reads
or touches any client's repo or computer.

What changes on the way:
- Each SOUL's shared part (AI Guy's own go-to-market charter: what it sells, its site, its team) becomes
  {{AGENT_CHARTER}}, which the computer fills with the client's project and agent charters. The profile's own
  working section stays.
- The profiles' own owner and business become {{OWNER}} and {{BUSINESS}}, filled per client on the computer.
- The CRM map loses AI Guy's location, campaigns, lanes and approved templates. The client's own replace them.
- Every scheduled job stays paused, as the source ships them.
The tarball is deterministic, so the same source commit always gives the same checksum.
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(os.environ.get("RCM_ENGINE_SRC") or Path.home() / "AI OS Market Share " / "AIOS" / "Our AIOS" / "agents" / "gtm-box")
PROFILES = {"reactivation": "opener", "reply": "replies", "sales": "closer", "deal": "deals"}
BOX = ["beat", "crm", "crm_cards", "crm_job", "crm_replies", "crm_stage", "crm_sweep", "deal_ledger", "goal",
       "preflight", "send_guard", "sender_client", "sender_route", "skool_track", "skool_worker", "spend_guard",
       "suppression", "write_env"]
NAMES = [(re.compile(r"\bJustin's\b"), "{{OWNER}}'s"), (re.compile(r"\bJustin\b"), "{{OWNER}}"),
         (re.compile(r"\bAI Guy\b"), "{{BUSINESS}}")]
CLEARED = {"location": "", "owner_user": "", "read_only_pipelines": [], "excluded_campaigns": [], "lanes": {},
           "lane_pages": {}, "campaign_pages": {}, "templates": {}}
SECRET = re.compile(r"(sk-ant-api|sk-or-v1-|pit-[0-9a-f]{8}|xoxb-|xapp-|ghp_|rk_live_|sk_live_)")


def source_commit():
    try:
        return subprocess.run(["git", "-C", str(SRC), "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def files():
    """(path in the bundle, bytes) for everything the engine carries."""
    out, replaced = [], 0
    for kit, name in PROFILES.items():
        base = SRC / "build" / name
        if not base.is_dir():
            raise SystemExit(f"no built profile at {base}: run the GTM box's build.py there first")
        for f in sorted(base.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                data = f.read_bytes()
                if f.suffix in (".md", ".json", ".yaml", ".yml", ".txt"):
                    text = data.decode()
                    if f.name == "SOUL.md":
                        at = text.find(f"\n# {name}:")
                        if at < 0:
                            raise SystemExit(f"{name}'s SOUL.md has no '# {name}:' section to keep")
                        text = "{{AGENT_CHARTER}}\n" + text[at:]
                    for pat, rep in NAMES:
                        text, n = pat.subn(rep, text)
                        replaced += n
                    data = text.encode()
                out.append((f"profiles/{name}/{f.relative_to(base)}", data))
    for mod in BOX:
        out.append((f"box/{mod}.py", (SRC / "box" / f"{mod}.py").read_bytes()))
    crm_map = json.loads((SRC / "crm-map.json").read_text())
    crm_map.update(CLEARED)
    crm_map["_comment"] = "The client's CRM map. rcm-engine keys sets the location; the rest is the CRM team's shape."
    out.append(("crm-map.template.json", (json.dumps(crm_map, indent=2) + "\n").encode()))
    for f in ("install.sh", "render.py", "rcm-engine"):
        out.append((f, (ROOT / "engine" / f).read_bytes()))
    return out, replaced


def build():
    items, replaced = files()
    version = f"0.1.0+{source_commit()}"
    manifest = {"version": version, "source": f"jbellsolutions/our-aios agents/gtm-box@{source_commit()}",
                "profiles": PROFILES, "names_replaced": replaced}
    items.append(("ENGINE.json", (json.dumps(manifest, indent=2) + "\n").encode()))
    leaks = [p for p, d in items if SECRET.search(d.decode("utf-8", "ignore"))]
    if leaks:
        raise SystemExit(f"refusing: something shaped like a key is in {leaks}")
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path, data in sorted(items):
            info = tarfile.TarInfo(f"engine/{path}")
            info.size, info.mtime, info.uid, info.gid, info.uname, info.gname = len(data), 0, 0, 0, "", ""
            info.mode = 0o755 if path in ("install.sh", "rcm-engine") else 0o644
            tar.addfile(info, io.BytesIO(data))
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0) as g:
        g.write(raw.getvalue())
    blob = gz.getvalue()
    return blob, version, manifest


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    blob, version, manifest = build()
    sha = hashlib.sha256(blob).hexdigest()
    name = "engine.tar.gz"
    lock_path = ROOT / "kit" / "engine.lock.json"
    if a.check:
        lock = json.loads(lock_path.read_text())
        ok = lock.get("sha256") == sha
        print(f"{'pin matches' if ok else 'pin differs'}: {sha} ({version})")
        return 0 if ok else 1
    (ROOT / "dist").mkdir(exist_ok=True)
    (ROOT / "dist" / name).write_bytes(blob)
    lock_path.write_text(json.dumps({
        "_comment": "The engine the install pins: built by scripts/build_engine.py from the GTM box's CRM team, carried in each client's pack (rcm pack), checked by sha256 on the computer.",
        "bundle": "pack", "file": name, "version": version, "sha256": sha, "source": manifest["source"],
        "repo": "", "tag": ""}, indent=2) + "\n")
    print(f"built dist/{name}: {len(blob):,} bytes, sha256 {sha}, {version}, {manifest['names_replaced']} names replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
