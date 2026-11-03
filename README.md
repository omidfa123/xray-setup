# VPN stack (Docker)

One Docker Compose stack, one container per part, all on host networking.

| Container | Port              | Role                                                           |
|-----------|-------------------|----------------------------------------------------------------|
| xray      | tcp/443           | VLESS + Vision + REALITY (looks like `www.samsung.com`). One user per exit |
| hysteria  | udp/8444          | Hysteria2 + Salamander, exits from this server                 |
| psiphon   | 127.0.0.1:1080    | Exit for the 🛡️ Psiphon config                                  |
| lantern   | 127.0.0.1:12346   | Exit for the 🏮 Lantern config (off by default)                 |
| monitor   | -                 | Collects traffic, client IPs, destinations, sessions and errors into `data/vpn.db` |
| sub       | tcp/`SUB_PORT`    | Subscription URL `http://IP:SUB_PORT/SUB_TOKEN` (any other path: 404) |

## Configs (one link + QR code each, in `clients/`)
`clients/qr/0-subscription-all-configs.png` / the first line of `clients/links.txt` is a subscription
with every config; apps re-download it every 12 h. Tip: in v2rayNG enable "update subscription via proxy"
so later updates go through the tunnel (the URL is plain HTTP).

| Link name                               | Exit                                               |
|-----------------------------------------|----------------------------------------------------|
| 🇫🇷 Direct · ⚡ fastest                  | This server's IP                                   |
| ☁️ WARP · 🔄 new IP every connection     | Cloudflare WARP, random account per connection     |
| 🛡️ Psiphon · 🇬🇧 GB exit                  | Psiphon network, pinned to the fastest region (TCP only) |
| 🏮 Lantern · 🌍 random country           | Lantern network (TCP only)                         |
| 🇫🇷 Hysteria2 · 🚀 UDP                   | This server's IP, over QUIC                        |

## Turn on WARP / Lantern
```bash
./warp-register.sh 4                  # registers 4 free WARP accounts -> warp/accounts.json
echo COMPOSE_PROFILES=lantern >> .env # enables the Lantern container and config
./render.sh && docker compose up -d --force-recreate
```
Lantern's free tier is data-limited.

## Fastest Psiphon country
```bash
./psiphon-bench.sh                 # all regions, 5 at a time (rough)
PAR=1 ./psiphon-bench.sh GB NL IT  # one at a time (fair)
# pin: set "EgressRegion" in psiphon/client.config ("" = random), then
./render.sh && docker compose up -d --force-recreate psiphon xray
```

## Everyday commands
```bash
docker compose ps                     # status
./report.sh                           # last 24h: traffic, speed, IPs, destinations, sessions, errors
./report.sh --days 30 --user warp     # one config, one month
./report.sh --sessions                # every session
./report.sh --live                    # speed right now
docker compose logs -f xray           # raw logs (also in logs/)
```

## Files
- `.env`: all secrets and settings. **After editing it, run** `./render.sh && docker compose up -d --force-recreate`
- `render.py` / `render.sh`: build `xray/config.json`, `hysteria/config.yaml`, `clients/links.txt` and `clients/qr/*.png`
- `monitor/`: collector (`monitor.py`) and report (`report.py`). Data is kept for 90 days
- `logs/`: Xray access/error logs and the Hysteria log, rotated daily by logrotate
- `bundle.sh`: `dist/vpn-bundle-*.tar` (images + everything, for moving) and `dist/vpn-docker-src-*.zip` (source only, no secrets)
- `install.sh`: installs Docker if needed, loads images, detects the new IP, renders and starts

## Move to another server
```bash
./bundle.sh
scp dist/vpn-bundle-*.tar root@NEW_SERVER:/root/
# on the new server:
cd /root && tar -xf vpn-bundle-*.tar && cd vpn-docker && ./install.sh   # add --new-keys for fresh keys
```
Keeping the keys means clients only need the new IP: re-import from `clients/`.

## Upgrade Xray / Hysteria
Bump `*_VERSION` and `*_SHA256` in the Dockerfile and the image tag in `docker-compose.yml` (and in
`render.sh`, `warp-register.sh`, `install.sh`, `monitor/Dockerfile` for Xray), then `docker compose build && docker compose up -d`.
# xray-setup
