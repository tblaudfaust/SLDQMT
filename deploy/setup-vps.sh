#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 22.04/24.04 VPS (Hostinger KVM) for the SLPHC Field Monitor system.
# Run as root on the VPS:
#   bash <(curl -fsSL https://raw.githubusercontent.com/tblaudfaust/SLDQMT/main/deploy/setup-vps.sh)
set -euo pipefail

REPO="${REPO:-https://github.com/tblaudfaust/SLDQMT.git}"
APP_DIR="${APP_DIR:-/opt/sldqmt}"

echo "== Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl git ufw
  if apt-cache show docker-compose-v2 >/dev/null 2>&1; then
    # Ubuntu's own packages (present on 24.04+ and needed on releases Docker's repo does not cover yet)
    apt-get install -y docker.io docker-compose-v2 docker-buildx
  else
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  fi
  systemctl enable --now docker
fi

echo "== Firewall: allow SSH, HTTP, HTTPS"
ufw allow OpenSSH >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "== Cloning $REPO into $APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone "$REPO" "$APP_DIR"
fi
cd "$APP_DIR"

if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
  sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$(openssl rand -hex 48)/" .env
  echo
  echo "!! Edit $APP_DIR/.env now: set DOMAIN to your domain (its DNS A record must point at this VPS)"
  echo "   and BOOTSTRAP_ADMIN_PASSWORD to the first admin password. Then run:"
  echo "   cd $APP_DIR && bash deploy/update.sh"
  exit 0
fi

bash deploy/update.sh
