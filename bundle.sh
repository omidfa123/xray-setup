#!/bin/sh
# Pack the stack for another server:
#   dist/vpn-bundle-<date>.tar   images + configs + keys. Copy it over, then:
#                                 tar -xf vpn-bundle-*.tar && cd vpn-docker && ./install.sh
#   dist/vpn-docker-src-<date>.zip  source only (Dockerfiles, compose, scripts), no images, no secrets
set -eu
cd "$(dirname "$0")"
D=$(date -u +%Y%m%d-%H%M)
mkdir -p dist
STAGE=$(mktemp -d); trap 'rm -rf "$STAGE"' EXIT

echo "== saving images"
docker image inspect local/lantern:1.2.8 >/dev/null 2>&1 || docker compose --profile lantern build lantern
docker save local/xray:v26.10.21 local/hysteria:v2.13.0 local/psiphon:host local/lantern:1.2.8 local/vpn-monitor:1 \
  | gzip -1 > "$STAGE/images.tar.gz"

echo "== packing files"
mkdir "$STAGE/vpn-docker"
tar -cf - --exclude=./dist --exclude=./logs --exclude=./data --exclude=./psiphon/data --exclude=./lantern/data . \
  | tar -xf - -C "$STAGE/vpn-docker"
mv "$STAGE/images.tar.gz" "$STAGE/vpn-docker/"
tar -cf "dist/vpn-bundle-$D.tar" -C "$STAGE" vpn-docker
chmod 600 "dist/vpn-bundle-$D.tar"

zip -qr "dist/vpn-docker-src-$D.zip" . -x 'dist/*' 'logs/*' 'data/*' 'psiphon/data/*' 'lantern/data/*' \
  '.env' 'warp/*' 'clients/*' 'xray/config.json' 'hysteria/config.yaml' 'hysteria/server.key'
ls -lh dist/*"$D"*
