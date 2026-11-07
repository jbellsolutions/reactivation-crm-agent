#!/usr/bin/env bash
# One command for the go-live writes Justin approved on 2026-11-07, once his keys are in this repo's .env.local.
#   bash scripts/go-live.sh
# Keys, each added by Justin with `add-secret NAME` from this folder (nothing here prints one):
#   STRIPE_SECRET_KEY      makes the $500 deposit link
#   STRIPE_READ_KEY        a restricted key that can only read Checkout sessions (the site and the poller)
#   NOTION_TOKEN           an integration with access to Command Center (writes and reads Signups and Builds)
#   CLOUDFLARE_API_TOKEN   and CLOUDFLARE_ACCOUNT_ID, to deploy the signup site
# Each step says what it did, and stops at the first one that can't run.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env.local ] || { echo "no .env.local: add the keys with add-secret first" >&2; exit 2; }
set -a; . ./.env.local; set +a
need() { for k in "$@"; do [ -n "${!k:-}" ] || { echo "missing $k: run add-secret $k" >&2; exit 2; }; done; }
PROJECT="reactivation-signup"
HOST="${RCM_SIGNUP_HOST:-$PROJECT.pages.dev}"

echo "1/4 Stripe deposit link"
need STRIPE_SECRET_KEY
if grep -q 'paymentLink: ""' web/public/config.js; then
  out="$(python3 scripts/golive.py stripe --signup-host "$HOST" --apply)"
  url="$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin)["url"])')"
  sed -i '' "s|paymentLink: \"\"|paymentLink: \"$url\"|" web/public/config.js
  echo "   made: $url"
else
  echo "   already set in web/public/config.js"
fi

echo "2/4 Signup site"
need CLOUDFLARE_API_TOKEN CLOUDFLARE_ACCOUNT_ID STRIPE_READ_KEY NOTION_TOKEN
(cd web && npx -y wrangler@4 pages project create "$PROJECT" --production-branch main >/dev/null 2>&1 || true)
for k in STRIPE_READ_KEY NOTION_TOKEN; do
  printf '%s' "${!k}" | (cd web && npx -y wrangler@4 pages secret put "$k" --project-name "$PROJECT" >/dev/null)
done
printf '%s' "${RCM_SIGNUPS_DS:-129d16fc-c867-4e30-b7e9-30633c302ba2}" | (cd web && npx -y wrangler@4 pages secret put RCM_SIGNUPS_DS --project-name "$PROJECT" >/dev/null)
(cd web && npx -y wrangler@4 pages deploy public --project-name "$PROJECT" --branch main --commit-dirty=true)
code="$(curl -s -o /dev/null -w '%{http_code}' "https://$HOST/")"
echo "   https://$HOST/ answers $code"

echo "3/4 Poller"
python3 -m rcm.cli poll --write-builds

echo "4/4 Poller schedule"
bash scripts/install-poller.sh
echo "done"
