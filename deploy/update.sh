#!/usr/bin/env bash
# Pull the latest code and rebuild/restart what changed.
# Safe to run any time on the VPS; GitHub Actions also runs it after every push to main.
set -euo pipefail
cd "$(dirname "$0")/.."

# Everything lives in a function so bash parses the whole file before running it:
# the git reset below replaces this very script, and bash would otherwise keep
# executing the old copy from its previous offset.
# The Android workflow attaches SLPHC-FieldMonitor-<tag>-<sha>.apk and SLPHC-ME-FieldTool-<tag>-<sha>.apk to every
# tag release; the server serves them from downloads/ under fixed names (see app/api/v1/resources.py).
fetch_apks() {
  local api="https://api.github.com/repos/tblaudfaust/SLDQMT/releases/latest"
  local json; json=$(curl -fsSL -H "Accept: application/vnd.github+json" "$api") || return 1
  mkdir -p downloads
  local name url
  for name in SLPHC-FieldMonitor SLPHC-ME-FieldTool; do
    url=$(printf '%s' "$json" | grep -o "\"browser_download_url\": *\"[^\"]*/$name-[^\"]*\.apk\"" | head -1 | sed 's/.*"\(https[^"]*\)"/\1/')
    [ -n "$url" ] || { echo "   no $name asset in the latest release"; continue; }
    # download when the release asset differs from the one we already serve (recorded in a sidecar file)
    if [ -f "downloads/$name.apk" ] && [ "$(cat "downloads/$name.apk.src" 2>/dev/null)" = "$url" ]; then
      echo "   downloads/$name.apk is current ($url)"; continue
    fi
    if curl -fsSL -o "downloads/$name.apk.tmp" "$url" && [ -s "downloads/$name.apk.tmp" ]; then
      mv -f "downloads/$name.apk.tmp" "downloads/$name.apk"; printf '%s' "$url" > "downloads/$name.apk.src"; echo "   updated downloads/$name.apk from $url"
    else
      rm -f "downloads/$name.apk.tmp"; echo "   could not download $url"
    fi
  done
}

main() {

  echo "== $(date -u +%FT%TZ) pulling latest main"
  git fetch --quiet origin main
  git reset --hard --quiet origin/main

  echo "== fetching the latest released APKs into downloads/ (GitHub release assets; kept if unchanged)"
  fetch_apks || echo "!! could not fetch the APKs (ignored)"

  echo "== building and restarting containers"
  docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
  docker image prune -f >/dev/null
  # a changed Caddyfile is bind-mounted, so Caddy must be told to reload it (new site names get their certificates here)
  docker compose -f docker-compose.prod.yml exec -T caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true

  echo "== waiting for the API"
  for _ in $(seq 1 30); do
    if docker compose -f docker-compose.prod.yml exec -T server python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" >/dev/null 2>&1; then
      echo "== healthy: $(git log -1 --format='%h %s')"
      # demo data of the M&E Field Tool (idempotent: loads once per version, see app/services/me_kpi_demo.py)
      docker compose -f docker-compose.prod.yml exec -T server python -m app.services.me_kpi_demo || echo "!! demo data step failed (ignored)"
      exit 0
    fi
    sleep 2
  done
  echo "!! API did not become healthy; recent server logs:"
  docker compose -f docker-compose.prod.yml logs --tail=50 server
  exit 1
}

main "$@"
