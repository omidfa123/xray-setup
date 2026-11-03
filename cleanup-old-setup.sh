#!/bin/sh
# Remove the pre-Docker VPN setup, leftover files, old logs and Docker caches.
# Everything removed from the old setup is archived first to /root/backups/old-setup-<date>.tar.gz.
set -eu
A=/root/backups/old-setup-$(date -u +%Y%m%d-%H%M%S).tar.gz
mkdir -p /root/backups

echo "== archiving old setup to $A"
tar -czpf "$A" --ignore-failed-read \
  /usr/local/bin/xray /usr/local/bin/hysteria /usr/local/bin/psiphon-tunnel-core /usr/local/bin/psiphon-healthcheck \
  /usr/local/etc/xray /usr/local/share/xray /etc/hysteria /etc/psiphon /var/lib/psiphon \
  /etc/systemd/system/xray.service /etc/systemd/system/hysteria.service /etc/systemd/system/psiphon.service \
  /etc/systemd/system/psiphon-health.service /etc/systemd/system/psiphon-health.timer \
  /root/vpn /root/vpn.tar /root/tunnel-backup.tar.gz 2>/dev/null || true
chmod 600 "$A"

echo "== removing old services, binaries, configs and users"
systemctl disable --now xray hysteria psiphon psiphon-health.timer 2>/dev/null || true
rm -f /etc/systemd/system/xray.service /etc/systemd/system/hysteria.service /etc/systemd/system/psiphon.service \
      /etc/systemd/system/psiphon-health.service /etc/systemd/system/psiphon-health.timer
systemctl daemon-reload; systemctl reset-failed
rm -f /usr/local/bin/xray /usr/local/bin/hysteria /usr/local/bin/psiphon-tunnel-core /usr/local/bin/psiphon-healthcheck
rm -rf /usr/local/etc/xray /usr/local/share/xray /etc/hysteria /etc/psiphon /var/lib/psiphon
for u in xray hysteria psiphon; do userdel "$u" 2>/dev/null || true; groupdel "$u" 2>/dev/null || true; done

echo "== removing leftover files in /root"
rm -rf /root/vpn /root/vpn.tar /root/tunnel-backup.tar.gz
rmdir /root/rust /root/ts 2>/dev/null || true   # empty folders

echo "== trimming logs (keeps current log files, drops rotated ones)"
journalctl --vacuum-time=1d -q
find /var/log -type f \( -name "*.gz" -o -name "*.[0-9]" -o -name "*.old" \) -delete

echo "== Docker and apt caches"
docker image prune -f >/dev/null
docker builder prune -af >/dev/null
apt-get clean

echo "== done"
journalctl --disk-usage; du -sh /var/log; df -h / | tail -1
