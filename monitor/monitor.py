#!/usr/bin/env python3
"""Collect VPN usage into /data/vpn.db every minute.

- traffic:     bytes per user (Xray users + "hysteria") and per Xray outbound, per minute
- connections: every Xray connection: time, user, client IP, destination, route
- hy_events:   Hysteria2 connects/disconnects (client IP, reason)
- errors:      rejected Xray connections, Xray warnings, Hysteria warnings/errors
"""
import calendar
import json
import os
import re
import sqlite3
import subprocess
import time
import urllib.request

DB = "/data/vpn.db"
XRAY_ACCESS = "/logs/xray/access.log"
XRAY_ERROR = "/logs/xray/error.log"
HY_LOG = "/logs/hysteria/hysteria.log"
INTERVAL = 60
KEEP_DAYS = int(os.environ.get("KEEP_DAYS", "90"))
HY_SECRET = os.environ.get("HY2_PASSWORD", "")

SCHEMA = """
CREATE TABLE IF NOT EXISTS traffic (ts INTEGER, kind TEXT, name TEXT, up INTEGER, down INTEGER);
CREATE INDEX IF NOT EXISTS traffic_ts ON traffic(ts);
CREATE TABLE IF NOT EXISTS connections (ts REAL, user TEXT, src_ip TEXT, net TEXT, dest TEXT, port INTEGER, route TEXT);
CREATE INDEX IF NOT EXISTS conn_ts ON connections(ts);
CREATE TABLE IF NOT EXISTS hy_events (ts REAL, event TEXT, user TEXT, src_ip TEXT, reason TEXT);
CREATE TABLE IF NOT EXISTS errors (ts REAL, source TEXT, user TEXT, src_ip TEXT, msg TEXT);
CREATE INDEX IF NOT EXISTS err_ts ON errors(ts);
CREATE TABLE IF NOT EXISTS offsets (path TEXT PRIMARY KEY, inode INTEGER, pos INTEGER);
"""

# 2026/11/03 13:07:18.123456 from 1.2.3.4:5678 accepted tcp:example.com:443 [vless-reality >> direct] email: direct
ACCESS_RE = re.compile(
    r"^(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d(?:\.\d+)?) from (?:tcp:|udp:)?\[?([0-9a-fA-F.:]+?)\]?:\d+ "
    r"(accepted|rejected)\s+(.*)$")
DEST_RE = re.compile(r"^(tcp|udp):(.+):(\d+) \[([^\]]*)\](?: email: (\S+))?")
XRAY_TS_RE = re.compile(r"^(\d{4}/\d\d/\d\d \d\d:\d\d:\d\d(?:\.\d+)?) (.*)$")
NUM_RE = re.compile(r"\b\d+\.\d+\.\d+\.\d+(:\d+)?\b|\[[0-9a-f:]+\](:\d+)?")


def xray_ts(s):
    # containers run in UTC, so log times are UTC
    base, _, frac = s.partition(".")
    return calendar.timegm(time.strptime(base, "%Y/%m/%d %H:%M:%S")) + (float("0." + frac) if frac else 0)


def iso_ts(s):
    base = s.rstrip("Z").split(".")[0]
    return calendar.timegm(time.strptime(base, "%Y-%m-%dT%H:%M:%S"))


def tail(db, path):
    """Yield new lines since last read; restart from 0 if the file was rotated or truncated."""
    try:
        st = os.stat(path)
    except FileNotFoundError:
        return
    row = db.execute("SELECT inode, pos FROM offsets WHERE path=?", (path,)).fetchone()
    pos = row[1] if row and row[0] == st.st_ino and row[1] <= st.st_size else 0
    with open(path, "r", errors="replace") as f:
        f.seek(pos)
        while True:
            line = f.readline()
            if not line or not line.endswith("\n"):
                break
            pos = f.tell()
            yield line.rstrip("\n")
    db.execute("INSERT OR REPLACE INTO offsets VALUES (?,?,?)", (path, st.st_ino, pos))


def collect_access(db):
    conns, errs = [], []
    for line in tail(db, XRAY_ACCESS):
        m = ACCESS_RE.match(line)
        if not m:
            continue
        ts, ip, status, rest = xray_ts(m.group(1)), m.group(2), m.group(3), m.group(4)
        if status == "rejected":
            errs.append((ts, "xray-reject", None, ip, NUM_RE.sub("IP", rest.strip())[:200]))
            continue
        d = DEST_RE.match(rest)
        if d:
            route = d.group(4).split(">>")[-1].strip()
            conns.append((ts, d.group(5) or "?", ip, d.group(1), d.group(2), int(d.group(3)), route))
    db.executemany("INSERT INTO connections VALUES (?,?,?,?,?,?,?)", conns)
    db.executemany("INSERT INTO errors VALUES (?,?,?,?,?)", errs)


def collect_xray_errors(db):
    errs = []
    for line in tail(db, XRAY_ERROR):
        m = XRAY_TS_RE.match(line)
        if m and ("[Warning]" in line or "[Error]" in line) and "core: Xray" not in line:
            errs.append((xray_ts(m.group(1)), "xray", None, None, NUM_RE.sub("IP", m.group(2))[:200]))
    db.executemany("INSERT INTO errors VALUES (?,?,?,?,?)", errs)


def collect_hysteria_log(db):
    events, errs = [], []
    for line in tail(db, HY_LOG):
        try:
            j = json.loads(line)
        except ValueError:
            continue
        t = j.get("time")
        ts = t / 1000 if isinstance(t, (int, float)) else iso_ts(t) if t else time.time()  # json format: epoch ms
        ip = (j.get("addr") or "").rsplit(":", 1)[0].strip("[]")
        msg = j.get("msg", "")
        if msg in ("client connected", "client disconnected"):
            events.append((ts, msg.split()[1], j.get("id"), ip, j.get("error")))
        elif j.get("level") in ("warn", "error"):
            detail = NUM_RE.sub("IP", str(j.get("error", "")))[:160]
            errs.append((ts, "hysteria", j.get("id"), ip, f"{msg}: {detail}"))
    db.executemany("INSERT INTO hy_events VALUES (?,?,?,?,?)", events)
    db.executemany("INSERT INTO errors VALUES (?,?,?,?,?)", errs)


def collect_traffic(db, now):
    rows = []
    try:
        out = subprocess.run(["xray", "api", "statsquery", "--server=127.0.0.1:10085", "-reset"],
                             capture_output=True, text=True, timeout=10).stdout
        acc = {}
        for s in json.loads(out or "{}").get("stat", []):
            kind, name, _, direction = s["name"].split(">>>")
            if kind in ("user", "outbound"):
                acc.setdefault((kind, name), [0, 0])[0 if direction == "uplink" else 1] += int(s.get("value", 0))
        rows += [(now, k, n, v[0], v[1]) for (k, n), v in acc.items() if v[0] or v[1]]
    except Exception as e:  # xray restarting: try again next minute
        print("xray stats:", e)
    try:
        req = urllib.request.Request("http://127.0.0.1:10086/traffic?clear=1", headers={"Authorization": HY_SECRET})
        for _, v in json.load(urllib.request.urlopen(req, timeout=5)).items():
            if v.get("tx") or v.get("rx"):
                # Hysteria counts from the client's side: tx = upload, rx = download
                rows.append((now, "user", "hysteria", v.get("tx", 0), v.get("rx", 0)))
    except Exception as e:
        print("hysteria stats:", e)
    db.executemany("INSERT INTO traffic VALUES (?,?,?,?,?)", rows)


def prune(db, now):
    cut = now - KEEP_DAYS * 86400
    for t in ("traffic", "connections", "hy_events", "errors"):
        db.execute(f"DELETE FROM {t} WHERE ts < ?", (cut,))


def main():
    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    last_prune = 0
    while True:
        now = int(time.time())
        for step in (collect_access, collect_xray_errors, collect_hysteria_log):
            try:
                step(db)
            except Exception as e:
                print(step.__name__, e)
        collect_traffic(db, now)
        if now - last_prune > 86400:
            prune(db, now)
            last_prune = now
        db.commit()
        time.sleep(INTERVAL - time.time() % INTERVAL)


if __name__ == "__main__":
    main()
