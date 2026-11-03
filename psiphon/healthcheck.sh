#!/bin/sh
# Probe the tunnel; after 2 failures in a row kill Psiphon so Docker restarts it.
STATE=/tmp/health.fail
if curl -fsS --max-time 10 --socks5-hostname 127.0.0.1:1080 -o /dev/null https://www.gstatic.com/generate_204; then
  rm -f "$STATE"; exit 0
fi
n=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$STATE"
if [ "$n" -ge 2 ]; then
  echo "psiphon unreachable twice in a row -- restarting"
  rm -f "$STATE"
  pkill -x psiphon-tunnel-core
fi
exit 1
