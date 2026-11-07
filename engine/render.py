#!/usr/bin/env python3
"""On the client's computer: render the CRM team's four profiles and the CRM map for one client.

    python3 render.py --bundle <unpacked engine> --manifest /root/.rcm/manifest.json --out /root/.rcm

The bundle carries the profiles with {{OWNER}} and {{BUSINESS}} where the source named its own owner and
business, and crm-map.template.json with no location. This fills both from the client's manifest. The
location comes later, from the client, at `rcm-engine keys`.
"""

import argparse
import json
import shutil
from pathlib import Path

TEXT = (".md", ".json", ".yaml", ".yml", ".txt")


def render_text(text, values):
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", v)
    return text


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    bundle, out = Path(a.bundle), Path(a.out)
    m = json.loads(Path(a.manifest).read_text())
    charters = Path(a.manifest).parent / "charters"
    shared = "\n\n".join((charters / f).read_text() for f in ("PROJECT-CHARTER.md", "AGENT-CHARTER.md")
                         if (charters / f).exists())
    values = {"OWNER": m["rcm"].get("owner_first_name") or "the owner", "BUSINESS": m["label"],
              "AGENT_CHARTER": shared or "Read CHARTER.md in this profile first."}

    for src in sorted((bundle / "profiles").iterdir()):
        dest = out / "build" / src.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        for f in dest.rglob("*"):
            if f.is_file() and f.suffix in TEXT:
                f.write_text(render_text(f.read_text(), values))

    crm_map = json.loads((bundle / "crm-map.template.json").read_text())
    crm_map["owner_user"] = values["OWNER"]
    target = out / "box" / "crm-map.json"
    if target.exists():
        crm_map["location"] = json.loads(target.read_text()).get("location", "")
    target.write_text(json.dumps(crm_map, indent=2) + "\n")
    print(f"rendered {len(list((out / 'build').iterdir()))} profiles for {values['BUSINESS']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
