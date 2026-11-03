#!/usr/bin/env python3
"""Render xray/config.json, hysteria/config.yaml, clients/links.txt and QR codes from .env.

Runs inside the monitor image (see render.sh), so the host needs only Docker.
Optional exits switch on by themselves:
  WARP    -> when warp/accounts.json exists (./warp-register.sh)
  Lantern -> when COMPOSE_PROFILES=lantern in .env
"""
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from urllib.parse import quote

ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(ROOT, ".env")


def load_env():
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def ensure(env, key, make):
    """Add a missing value to .env so it stays stable across renders."""
    if not env.get(key):
        env[key] = make()
        with open(ENV_PATH, "a") as f:
            f.write(f"{key}={env[key]}\n")


def flag(cc):
    cc = (cc or "").upper()
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc) if len(cc) == 2 and cc.isalpha() else "🏠"


def write(path, text, mode=0o600):
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)
    os.chmod(full, mode)


env = load_env()
ensure(env, "UUID_WARP", lambda: str(uuid.uuid4()))
ensure(env, "UUID_LANTERN", lambda: str(uuid.uuid4()))

warp_path = os.path.join(ROOT, "warp", "accounts.json")
warp = json.load(open(warp_path)) if os.path.exists(warp_path) else []
lantern = "lantern" in env.get("COMPOSE_PROFILES", "")
cc = env.get("SERVER_COUNTRY", "")
city = env.get("SERVER_CITY", "")
where = " ".join(x for x in (city, cc) if x)

# (email, uuid, outbound or balancer, link name)
users = [("direct", env["UUID_DIRECT"], "direct", f"{flag(cc)} Direct · {where} · ⚡ fastest")]
if warp:
    users.append(("warp", env["UUID_WARP"], "warp-pool", "☁️ WARP · 🔄 new IP every connection"))
ps_region = json.load(open(os.path.join(ROOT, "psiphon", "client.config"))).get("EgressRegion", "")
ps_where = f"{flag(ps_region)} {ps_region} exit" if ps_region else "🌍 random country"
users.append(("psiphon", env["UUID_PSIPHON"], "psiphon", f"🛡️ Psiphon · {ps_where} · TCP only"))
if lantern:
    users.append(("lantern", env["UUID_LANTERN"], "lantern", "🏮 Lantern · 🌍 random country · 🐢 TCP only"))

# ---- Xray ------------------------------------------------------------------
outbounds = [
    {"tag": "direct", "protocol": "freedom", "streamSettings": {"sockopt": {"domainStrategy": "UseIPv4"}}},
    {"tag": "psiphon", "protocol": "socks", "settings": {"servers": [{"address": "127.0.0.1", "port": 1080}]}},
    {"tag": "block", "protocol": "blackhole"},
]
if lantern:
    outbounds.append({"tag": "lantern", "protocol": "socks",
                      "settings": {"servers": [{"address": "127.0.0.1", "port": 12346}]}})
for i, a in enumerate(warp, 1):
    outbounds.append({
        "tag": f"warp-{i}",
        "protocol": "wireguard",
        "settings": {
            "secretKey": a["private_key"],
            "address": [a["v4"] + "/32", a["v6"] + "/128"],
            "peers": [{"publicKey": a["peer_public_key"], "endpoint": a["endpoint"],
                       "allowedIPs": ["0.0.0.0/0", "::/0"]}],
            "reserved": a["reserved"],
            "mtu": 1280,
        },
    })

rules = [
    {"inboundTag": ["api"], "outboundTag": "api"},
    {"ip": ["geoip:private"], "outboundTag": "block"},
    {"protocol": ["bittorrent"], "outboundTag": "block"},
]
for email, _, target, _ in users:
    if email in ("psiphon", "lantern"):  # their local SOCKS proxies carry TCP only
        rules.append({"user": [email], "network": "udp", "outboundTag": "block"})
    if email != "direct":
        key = "balancerTag" if target == "warp-pool" else "outboundTag"
        rules.append({"user": [email], key: target})

xray = {
    "log": {"loglevel": "warning", "access": "/var/log/xray/access.log", "error": "/var/log/xray/error.log"},
    "api": {"tag": "api", "listen": "127.0.0.1:10085", "services": ["StatsService"]},
    "stats": {},
    "policy": {
        "levels": {"0": {"handshake": 4, "connIdle": 300, "statsUserUplink": True, "statsUserDownlink": True}},
        "system": {"statsInboundUplink": True, "statsInboundDownlink": True,
                   "statsOutboundUplink": True, "statsOutboundDownlink": True},
    },
    "inbounds": [{
        "tag": "vless-reality", "listen": "0.0.0.0", "port": 443, "protocol": "vless",
        "settings": {"clients": [{"id": u, "email": e, "flow": "xtls-rprx-vision"} for e, u, _, _ in users],
                     "decryption": "none"},
        "streamSettings": {"network": "tcp", "security": "reality", "realitySettings": {
            "target": f"{env['REALITY_TARGET']}:443", "serverNames": [env["REALITY_TARGET"]],
            "privateKey": env["REALITY_PRIVATE_KEY"], "shortIds": [env["REALITY_SHORT_ID"]]}},
        "sniffing": {"enabled": True, "destOverride": ["http", "tls", "quic"], "routeOnly": True},
    }],
    "outbounds": outbounds,
    "routing": {"domainStrategy": "AsIs", "rules": rules},
}
if warp:
    xray["routing"]["balancers"] = [{"tag": "warp-pool", "selector": ["warp-"], "strategy": {"type": "random"}}]
write("xray/config.json", json.dumps(xray, indent=2, ensure_ascii=False) + "\n", 0o644)

# ---- Hysteria --------------------------------------------------------------
with open(os.path.join(ROOT, "hysteria", "config.template.yaml")) as f:
    hy = f.read()
for k in ("HY2_PASSWORD", "HY2_OBFS_PASSWORD"):
    hy = hy.replace("${" + k + "}", env[k])
write("hysteria/config.yaml", hy, 0o644)

# ---- Client links + QR codes -----------------------------------------------
def cert_pin(path):
    """SHA-256 of the certificate's DER bytes, as Hysteria's pinSHA256 expects."""
    import base64
    pem = open(path).read()
    b64 = pem.split("-----BEGIN CERTIFICATE-----")[1].split("-----END CERTIFICATE-----")[0]
    return hashlib.sha256(base64.b64decode("".join(b64.split()))).hexdigest()


ip = env["SERVER_IP"]
q = ("encryption=none&flow=xtls-rprx-vision&security=reality"
     f"&sni={env['REALITY_TARGET']}&fp=chrome&pbk={env['REALITY_PUBLIC_KEY']}&sid={env['REALITY_SHORT_ID']}&type=tcp")
links = [(name, f"vless://{u}@{ip}:443?{q}#{quote(name)}") for _, u, _, name in users]
hy_name = f"{flag(cc)} Hysteria2 · {where} · 🚀 UDP · use if TCP is slow"
links.append((hy_name,
              f"hysteria2://{env['HY2_PASSWORD']}@{ip}:8444/?insecure=1"
              f"&pinSHA256={cert_pin(os.path.join(ROOT, 'hysteria', 'server.crt'))}"
              f"&sni=www.bing.com&obfs=salamander&obfs-password={env['HY2_OBFS_PASSWORD']}#{quote(hy_name)}"))

qr_dir = os.path.join(ROOT, "clients", "qr")
shutil.rmtree(qr_dir, ignore_errors=True)
os.makedirs(qr_dir, mode=0o700)
text = []
for n, (name, link) in enumerate(links, 1):
    text += [f"# {name}", link, ""]
    slug = "".join(c if c.isascii() and c.isalnum() else "-" for c in name).strip("-").lower()
    slug = "-".join(p for p in slug.split("-") if p)
    subprocess.run(["qrencode", "-o", os.path.join(qr_dir, f"{n}-{slug}.png"), "-s", "8", "-m", "2", link], check=True)
# ---- Subscription (served by the "sub" container) ---------------------------
import base64  # noqa: E402
import random  # noqa: E402
import secrets  # noqa: E402
ensure(env, "SUB_TOKEN", lambda: secrets.token_urlsafe(18))
ensure(env, "SUB_PORT", lambda: str(random.randint(20000, 60000)))
sub_url = f"http://{ip}:{env['SUB_PORT']}/{env['SUB_TOKEN']}"
write("clients/sub/sub.txt", base64.b64encode("\n".join(l for _, l in links).encode()).decode() + "\n", 0o644)
os.chmod(os.path.join(ROOT, "clients", "sub"), 0o755)
subprocess.run(["qrencode", "-o", os.path.join(qr_dir, "0-subscription-all-configs.png"), "-s", "8", "-m", "2", sub_url],
               check=True)
text = ["# 📥 Subscription · all configs, auto-updates", sub_url, ""] + text
write("clients/links.txt", "\n".join(text))

print(f"rendered {len(users)} Xray exits ({', '.join(e for e, *_ in users)}) + Hysteria2;"
      f" {len(links)} links, subscription and QR codes in clients/")
print(f"subscription: {sub_url}")
