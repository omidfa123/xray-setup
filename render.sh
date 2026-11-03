#!/bin/sh
# Render server configs, client links and QR codes from .env (runs in the monitor image).
set -eu
cd "$(dirname "$0")"
docker run --rm -v "$PWD:/work" --entrypoint python3 local/vpn-monitor:1 -I /work/render.py
