#!/usr/bin/env bash
# Pull the latest code and rebuild/restart what changed.
# Safe to run any time on the VPS; GitHub Actions also runs it after every push to main.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== $(date -u +%FT%TZ) pulling latest main"
git fetch --quiet origin main
git reset --hard --quiet origin/main

echo "== building and restarting containers"
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans
docker image prune -f >/dev/null

echo "== waiting for the API"
for _ in $(seq 1 30); do
  if docker compose -f docker-compose.prod.yml exec -T server python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health', timeout=3)" >/dev/null 2>&1; then
    echo "== healthy: $(git log -1 --format='%h %s')"
    exit 0
  fi
  sleep 2
done
echo "!! API did not become healthy; recent server logs:"
docker compose -f docker-compose.prod.yml logs --tail=50 server
exit 1
