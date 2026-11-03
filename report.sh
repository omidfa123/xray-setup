#!/bin/sh
# Usage report. Examples:
#   ./report.sh                    last 24h, everything
#   ./report.sh --days 30          last month
#   ./report.sh --user warp        one config only (direct, warp, psiphon, lantern, hysteria)
#   ./report.sh --sessions         list every session
#   ./report.sh --live             speed in the last 5 minutes
exec docker exec monitor python3 /app/report.py "$@"
