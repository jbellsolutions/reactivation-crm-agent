#!/usr/bin/env bash
# The engine's installer, run as root on the client's Orgo Linux computer by the kit (rcm install).
#   bash install.sh --client <slug>
# Installs Hermes at a pinned commit if it's missing, the CRM team's box scripts, and the spend guard. Then it
# renders the four profiles for this client from /root/.rcm/manifest.json, which the kit's charters step puts
# there. Every scheduled job installs paused. Safe to run again.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CLIENT=""
while [ $# -gt 0 ]; do case "$1" in --client) CLIENT="$2"; shift 2 ;; *) shift ;; esac; done
[ -n "$CLIENT" ] || { echo "install.sh needs --client <slug>" >&2; exit 2; }
[ "$(uname -s)" = "Linux" ] || { echo "this belongs on the Orgo Linux computer" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "run as root (Orgo computers run their desktop as root)" >&2; exit 2; }

export GTM_HOME="${GTM_HOME:-/root/.rcm}"
MANIFEST="$GTM_HOME/manifest.json"
[ -f "$MANIFEST" ] || { echo "no $MANIFEST: the kit's charters step puts it there first" >&2; exit 2; }

# Hermes, pinned. The same public installer and commit the Orgo agent template pins.
HERMES_TAG="v2026.8.31"
HERMES_COMMIT="29112bef099274229cadff79cdff7bf7b99c4b77"
INSTALLER_SHA256="85ef536d455e51ab67aa74d79272efd49fe717597dbaadfd3cca179a905f4706"
if ! command -v hermes >/dev/null; then
  for p in git curl python3 python3-venv; do dpkg -s "$p" >/dev/null 2>&1 || NEED="${NEED:-} $p"; done
  [ -z "${NEED:-}" ] || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $NEED >/dev/null; }
  inst="$(mktemp)"
  curl -fsSL "https://raw.githubusercontent.com/NousResearch/hermes-agent/$HERMES_COMMIT/scripts/install.sh" -o "$inst"
  [ "$(sha256sum "$inst" | awk '{print $1}')" = "$INSTALLER_SHA256" ] || { echo "Hermes installer checksum mismatch" >&2; exit 3; }
  bash "$inst" --skip-setup --branch "$HERMES_TAG" --commit "$HERMES_COMMIT" --force-commit
fi
command -v hermes >/dev/null || { echo "Hermes didn't install" >&2; exit 3; }

mkdir -p "$GTM_HOME/box" "$GTM_HOME/heartbeat" "$GTM_HOME/ledger" "$GTM_HOME/build" "$GTM_HOME/crm"
chmod 700 "$GTM_HOME"
cp "$HERE"/box/*.py "$GTM_HOME/box/"
python3 "$HERE/render.py" --bundle "$HERE" --manifest "$MANIFEST" --out "$GTM_HOME"

# The spend guard holds the client's model key and the daily cap; the profiles talk only to it.
if command -v supervisorctl >/dev/null; then
  cat > /etc/supervisor/conf.d/rcm-spend-guard.conf <<EOF
[program:rcm-spend-guard]
command=python3 $GTM_HOME/box/spend_guard.py serve
environment=GTM_HOME="$GTM_HOME",GTM_DAILY_CAP="${RCM_DAILY_CAP:-5}"
autorestart=true
EOF
  supervisorctl reread >/dev/null && supervisorctl update >/dev/null || true
fi

install -m 755 "$HERE/rcm-engine" /usr/local/bin/rcm-engine
cp "$HERE/ENGINE.json" "$GTM_HOME/ENGINE.json"
echo "engine $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$HERE/ENGINE.json") installed for $CLIENT"
