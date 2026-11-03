#!/bin/sh
# Register N free Cloudflare WARP accounts into warp/accounts.json (default 4).
# Xray load-balances randomly across them, so each new connection can exit from a different IP.
set -eu
cd "$(dirname "$0")"
N=${1:-4}
API=https://api.cloudflareclient.com/v0a2158
mkdir -p warp; umask 077
echo "[]" > warp/accounts.json.new

i=1
while [ "$i" -le "$N" ]; do
  keys=$(docker run --rm --entrypoint xray local/xray:v26.10.21 wg)
  priv=$(echo "$keys" | awk -F': ' '/^PrivateKey/{print $2}')
  pub=$(echo "$keys" | awk -F': ' '/PublicKey/{print $2}')
  resp=$(curl -fsS -m20 -X POST "$API/reg" \
    -H 'User-Agent: okhttp/3.12.1' -H 'CF-Client-Version: a-6.10-2158' -H 'Content-Type: application/json' \
    -d "{\"key\":\"$pub\",\"install_id\":\"\",\"fcm_token\":\"\",\"tos\":\"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",\"model\":\"PC\",\"serial_number\":\"\",\"locale\":\"en_US\"}")
  # client_id is 3 raw bytes in base64; jq's @base64d would mangle them as UTF-8
  reserved=$(echo "$resp" | jq -r .config.client_id | base64 -d | od -An -tu1 | xargs | tr ' ' ,)
  echo "$resp" | jq --arg priv "$priv" --argjson reserved "[$reserved]" '{
      private_key: $priv,
      v4: .config.interface.addresses.v4,
      v6: .config.interface.addresses.v6,
      peer_public_key: .config.peers[0].public_key,
      endpoint: .config.peers[0].endpoint.host,
      reserved: $reserved,
      id: .id, token: .token }' > warp/one.json
  jq -s '.[0] + [.[1]]' warp/accounts.json.new warp/one.json > warp/tmp.json && mv warp/tmp.json warp/accounts.json.new
  echo "registered WARP account $i/$N"
  i=$((i + 1)); sleep 2
done
rm -f warp/one.json; mv warp/accounts.json.new warp/accounts.json
