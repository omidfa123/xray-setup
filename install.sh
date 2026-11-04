#!/bin/sh
# Install or move this VPN stack onto a server (Debian/Ubuntu).
#   ./install.sh              keep the same keys (clients only need the new IP)
#   ./install.sh --new-keys   fresh REALITY keys, UUIDs and passwords (old links stop working)
set -eu
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "== installing Docker"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq docker.io docker-cli >/dev/null 2>&1 || apt-get install -y -qq docker.io
  apt-get install -y -qq docker-compose-plugin >/dev/null 2>&1 || apt-get install -y -qq docker-compose
  systemctl enable --now docker
fi

if [ -f images.tar.gz ]; then
  echo "== loading images"
  gunzip -c images.tar.gz | docker load
fi
docker image inspect local/vpn-monitor:1 >/dev/null 2>&1 || { docker compose build xray && docker compose --profile lantern build; }

# Anything still holding our ports (an older install) must go first.
for u in gost xray hysteria psiphon psiphon-health.timer; do
  systemctl disable --now "$u" >/dev/null 2>&1 || true
done

setenv() {  # setenv KEY VALUE: replace or append in .env
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}

if [ "${1:-}" = "--new-keys" ]; then
  echo "== generating new keys"
  K=$(docker run --rm --entrypoint xray local/xray:v26.10.21 x25519)
  setenv REALITY_PRIVATE_KEY "$(echo "$K" | awk -F': ' '/^PrivateKey/{print $2}')"
  setenv REALITY_PUBLIC_KEY "$(echo "$K" | awk -F': ' '/PublicKey/{print $2}')"
  setenv REALITY_SHORT_ID "$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  for k in UUID_DIRECT UUID_WARP UUID_PSIPHON UUID_LANTERN; do
    setenv "$k" "$(docker run --rm --entrypoint xray local/xray:v26.10.21 uuid)"
  done
  setenv HY2_PASSWORD "$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  setenv HY2_OBFS_PASSWORD "$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi

echo "== detecting this server's public IP"
INFO=$(curl -4 -fsS -m 10 https://ipinfo.io/json || true)
IP=$(echo "$INFO" | sed -n 's/.*"ip": *"\([^"]*\)".*/\1/p')
[ -n "$IP" ] || IP=$(curl -4 -fsS -m 10 https://api.ipify.org)
setenv SERVER_IP "$IP"
setenv SERVER_COUNTRY "$(echo "$INFO" | sed -n 's/.*"country": *"\([^"]*\)".*/\1/p')"
setenv SERVER_CITY "$(echo "$INFO" | sed -n 's/.*"city": *"\([^"]*\)".*/\1/p' | tr -d ' ')"

mkdir -p logs/xray logs/hysteria data psiphon/data lantern/data
chmod 700 . && chmod 600 .env
install -m 644 logrotate.conf /etc/logrotate.d/vpn-docker 2>/dev/null || true
sed -i "s|/root/vpn-docker|$PWD|g" /etc/logrotate.d/vpn-docker 2>/dev/null || true

./render.sh
docker compose up -d --force-recreate --remove-orphans
echo
echo "== done: $IP"
docker compose ps --format "table {{.Name}}\t{{.Status}}"
echo
echo "Links:    $PWD/clients/links.txt"
echo "QR codes: $PWD/clients/qr/"
