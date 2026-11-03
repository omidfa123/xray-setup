#!/usr/bin/env python3
"""Serve clients/sub/sub.txt at http://<ip>:SUB_PORT/SUB_TOKEN. Any other path gets a plain 404.

Adds the headers v2rayNG / Hiddify / Streisand read: profile title, update interval,
and traffic used so far this month (from the monitor's vpn.db).
"""
import base64
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ["SUB_TOKEN"]
PORT = int(os.environ["SUB_PORT"])
SUB = "/sub/sub.txt"
DB = "/data/vpn.db"
TITLE = "base64:" + base64.b64encode("🛰️ My VPN".encode()).decode()


def month_usage():
    try:
        start = time.mktime(time.strptime(time.strftime("%Y-%m-01"), "%Y-%m-%d"))
        db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        up, down = db.execute("SELECT COALESCE(SUM(up),0), COALESCE(SUM(down),0) FROM traffic "
                              "WHERE kind='user' AND ts>=?", (start,)).fetchone()
        return int(up), int(down)
    except Exception:
        return 0, 0


class Handler(BaseHTTPRequestHandler):
    server_version = "nginx"
    sys_version = ""

    def do_GET(self):
        if self.path.split("?")[0].strip("/") != TOKEN:
            self.send_error(404, "Not Found")
            return
        body = open(SUB, "rb").read()
        up, down = month_usage()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("profile-title", TITLE)
        self.send_header("profile-update-interval", "12")
        self.send_header("subscription-userinfo", f"upload={up}; download={down}; total=0; expire=0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        if args and "/" + TOKEN in str(args[0]):
            print(f"{self.address_string()} fetched subscription")


ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
