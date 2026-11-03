#!/bin/sh
# Benchmark Psiphon exit regions from this server: connect time, latency and download speed.
#   ./psiphon-bench.sh              all regions Psiphon offers
#   ./psiphon-bench.sh DE NL GB     only these (PAR=1 to test one at a time, for fair speeds)
# Runs temporary Psiphon containers (5 at a time) next to the live one; nothing live is changed.
# To pin the winner: set "EgressRegion" in psiphon/client.config, then: docker compose restart psiphon
set -u
cd "$(dirname "$0")"
REGIONS=${*:-$(docker logs psiphon 2>&1 | grep -m1 AvailableEgressRegions | jq -r '.data.regions[]')}
PAR=${PAR:-5}
OUT=$(mktemp -d)
URL="https://speed.cloudflare.com/__down?bytes=10000000"

bench() {  # bench REGION PORT
  r=$1; port=$2
  jq --arg r "$r" --argjson p "$port" '.EgressRegion=$r | .LocalSocksProxyPort=$p | .LocalHttpProxyPort=0' \
    psiphon/client.config > "$OUT/$r.json"
  docker run -d --rm --name "pbench-$r" --network host --tmpfs /d -v "$OUT/$r.json:/c.json:ro" \
    --entrypoint /usr/local/bin/psiphon-tunnel-core local/psiphon:host -config /c.json -dataRootDirectory /d >/dev/null
  t0=$(date +%s); ok=""
  while [ $(( $(date +%s) - t0 )) -lt 90 ]; do
    if curl -fsS -m 8 --socks5-hostname "127.0.0.1:$port" -o /dev/null https://www.gstatic.com/generate_204 2>/dev/null; then ok=1; break; fi
    sleep 3
  done
  conn=$(( $(date +%s) - t0 ))
  if [ -z "$ok" ]; then
    echo "$r - - - - no-tunnel" > "$OUT/$r.res"
  else
    lat=$(for i in 1 2 3; do curl -s -m 10 --socks5-hostname "127.0.0.1:$port" -o /dev/null -w "%{time_total}\n" https://www.gstatic.com/generate_204; done \
          | sort -n | sed -n 2p | awk '{printf "%.0f", $1*1000}')
    sp=$(curl -s -m 45 --socks5-hostname "127.0.0.1:$port" -o /dev/null -w "%{speed_download}" "$URL" | awk '{printf "%.1f", $1*8/1e6}')
    ip=$(curl -s -m 10 --socks5-hostname "127.0.0.1:$port" https://www.cloudflare.com/cdn-cgi/trace | sed -n 's/^ip=//p')
    echo "$r $sp $lat $conn ${ip:-?} ok" > "$OUT/$r.res"
  fi
  docker rm -f "pbench-$r" >/dev/null 2>&1
}

i=0; port=21100
for r in $REGIONS; do
  bench "$r" "$port" &
  i=$((i + 1)); port=$((port + 1))
  [ $((i % PAR)) -eq 0 ] && wait
done
wait

echo "region  Mbit/s  latency_ms  connect_s  exit_ip"
cat "$OUT"/*.res | sort -k2 -rn | awk '{printf "%-7s %6s  %10s  %9s  %s %s\n", $1, $2, $3, $4, $5, ($6=="ok"?"":$6)}'
rm -rf "$OUT"
