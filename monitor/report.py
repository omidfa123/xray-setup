#!/usr/bin/env python3
"""VPN usage report from /data/vpn.db.

  report.py [--days N] [--user NAME] [--sessions] [--live]

Sections: traffic per user, speed (per-minute avg/peak), client IPs, top destinations,
sessions (connections from one IP with gaps under 5 minutes), and errors.
"""
import argparse
import sqlite3
import time

GAP = 300  # seconds of silence that ends a session


def mb(b):
    b = b or 0
    return f"{b / 1e9:8.2f} GB" if b >= 1e9 else f"{b / 1e6:8.1f} MB"


def mbit(bytes_per_min):
    return f"{(bytes_per_min or 0) * 8 / 60 / 1e6:6.1f} Mbit/s"


def when(ts):
    return time.strftime("%m-%d %H:%M", time.gmtime(ts))


def dur(s):
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}m{s % 60:02d}s"


def section(title):
    print(f"\n━━ {title} " + "━" * max(0, 60 - len(title)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=1)
    ap.add_argument("--user")
    ap.add_argument("--sessions", action="store_true", help="list every session")
    ap.add_argument("--live", action="store_true", help="speed in the last minutes only")
    a = ap.parse_args()
    db = sqlite3.connect("file:/data/vpn.db?mode=ro", uri=True)
    since = time.time() - a.days * 86400
    uf, up = ("AND name=?", [a.user]) if a.user else ("", [])
    cf, cp = ("AND user=?", [a.user]) if a.user else ("", [])

    if a.live:
        section("Live speed (last 5 minutes, per minute)")
        rows = db.execute("SELECT ts, name, up, down FROM traffic WHERE kind='user' AND ts>=? "
                          f"{uf} ORDER BY ts", [time.time() - 330] + up).fetchall()
        for ts, n, u, d in rows:
            print(f"  {when(ts)}  {n:<10} ↓ {mbit(d)}  ↑ {mbit(u)}")
        return

    print(f"VPN report · last {a.days:g} day(s) · times in UTC")

    section("Traffic per user")
    for n, u, d, mins, peak in db.execute(
            "SELECT name, SUM(up), SUM(down), COUNT(*), MAX(down) FROM traffic "
            f"WHERE kind='user' AND ts>=? {uf} GROUP BY name ORDER BY SUM(down) DESC", [since] + up):
        avg = d / mins if mins else 0
        print(f"  {n:<10} ↓{mb(d)}  ↑{mb(u)}  total{mb(u + d)}  "
              f"avg ↓{mbit(avg)}  peak ↓{mbit(peak)}  active {mins} min")

    section("Traffic per exit (Xray outbounds)")
    for n, u, d in db.execute("SELECT name, SUM(up), SUM(down) FROM traffic WHERE kind='outbound' AND ts>=? "
                              "GROUP BY name ORDER BY SUM(down) DESC", [since]):
        print(f"  {n:<10} ↓{mb(d)}  ↑{mb(u)}")

    section("Traffic per day")
    for day, d, u in db.execute(
            "SELECT date(ts,'unixepoch'), SUM(down), SUM(up) FROM traffic "
            f"WHERE kind='user' AND ts>=? {uf} GROUP BY 1 ORDER BY 1", [since] + up):
        print(f"  {day}  ↓{mb(d)}  ↑{mb(u)}")

    section("Client IPs")
    for user, ip, n, first, last in db.execute(
            "SELECT user, src_ip, COUNT(*), MIN(ts), MAX(ts) FROM connections "
            f"WHERE ts>=? {cf} GROUP BY user, src_ip ORDER BY COUNT(*) DESC LIMIT 25", [since] + cp):
        print(f"  {user:<10} {ip:<40} {n:>7} conns  {when(first)} → {when(last)}")
    for user, ip, n in db.execute(
            "SELECT user, src_ip, COUNT(*) FROM hy_events WHERE event='connected' AND ts>=? "
            "GROUP BY user, src_ip ORDER BY 3 DESC LIMIT 10", [since]):
        print(f"  hysteria   {ip:<40} {n:>7} sessions")

    section("Top destinations")
    for user, dest, n in db.execute(
            "SELECT user, dest, COUNT(*) FROM connections "
            f"WHERE ts>=? {cf} GROUP BY user, dest ORDER BY 3 DESC LIMIT 25", [since] + cp):
        print(f"  {user:<10} {n:>7}  {dest}")

    section("Sessions")
    conns = db.execute(f"SELECT user, src_ip, ts FROM connections WHERE ts>=? {cf} ORDER BY user, src_ip, ts",
                       [since] + cp).fetchall()
    traffic = db.execute(f"SELECT name, ts, up+down FROM traffic WHERE kind='user' AND ts>=? {uf}",
                         [since] + up).fetchall()
    sessions, cur = [], None
    for user, ip, ts in conns:
        if cur and cur[0] == user and cur[1] == ip and ts - cur[3] < GAP:
            cur[3], cur[4] = ts, cur[4] + 1
        else:
            cur = [user, ip, ts, ts, 1]
            sessions.append(cur)
    for s in sessions:  # bytes of the user's minutes that fall inside the session (approximate)
        s.append(sum(b for n, t, b in traffic if n == s[0] and s[2] - 60 <= t <= s[3] + 60))
    sessions.sort(key=lambda s: s[2], reverse=True)
    total = sum(s[3] - s[2] for s in sessions)
    print(f"  {len(sessions)} sessions, {dur(total)} total, avg {dur(total / len(sessions)) if sessions else '0m'}")
    for user, ip, start, end, n, b in sessions if a.sessions else sessions[:15]:
        print(f"  {when(start)} → {when(end)}  {dur(end - start):>7}  {user:<10} {ip:<40} {n:>6} conns ~{mb(b)}")
    hy = db.execute("SELECT ts, event, src_ip, reason FROM hy_events WHERE ts>=? ORDER BY src_ip, ts",
                    [since]).fetchall()
    opened, hs = {}, []
    for ts, ev, ip, _ in hy:
        if ev == "connected":
            opened[ip] = ts
        elif ip in opened:
            hs.append((opened.pop(ip), ts, ip))
    if hs:
        print(f"  hysteria: {len(hs)} sessions")
        for start, end, ip in sorted(hs, reverse=True)[:10]:
            print(f"  {when(start)} → {when(end)}  {dur(end - start):>7}  hysteria   {ip}")

    section("Errors")
    for src, msg, n, last in db.execute(
            "SELECT source, msg, COUNT(*), MAX(ts) FROM errors WHERE ts>=? GROUP BY source, msg "
            "ORDER BY 3 DESC LIMIT 20", [since]):
        print(f"  {n:>6}× {src:<11} last {when(last)}  {msg[:110]}")


if __name__ == "__main__":
    main()
