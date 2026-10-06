#!/usr/bin/env bash
# Pull the latest code and rebuild/restart what changed.
# Safe to run any time on the VPS; GitHub Actions also runs it after every push to main.
set -euo pipefail
cd "$(dirname "$0")/.."

# Everything lives in a function so bash parses the whole file before running it:
# the git reset below replaces this very script, and bash would otherwise keep
# executing the old copy from its previous offset.
main() {

  echo "== $(date -u +%FT%TZ) pulling latest main"
  git fetch --quiet origin main
  git reset --hard --quiet origin/main

  echo "== building and restarting containers"
  docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
  docker image prune -f >/dev/null
  # a changed Caddyfile is bind-mounted, so Caddy must be told to reload it (new site names get their certificates here)
  docker compose -f docker-compose.prod.yml exec -T caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true

  echo "== waiting for the API"
  for _ in $(seq 1 30); do
    if docker compose -f docker-compose.prod.yml exec -T server python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" >/dev/null 2>&1; then
      echo "== healthy: $(git log -1 --format='%h %s')"
      exit 0
    fi
    sleep 2
  done
  echo "!! API did not become healthy; recent server logs:"
  docker compose -f docker-compose.prod.yml logs --tail=50 server
  exit 1
}

main "$@"
