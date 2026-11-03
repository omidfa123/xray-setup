# Collector + tools image: xray CLI (stats API), python3 (monitor, report, render), qrencode (QR codes).
FROM local/xray:v26.10.21 AS xray

FROM alpine:3.20
RUN apk add --no-cache python3 libqrencode-tools ca-certificates tzdata
COPY --from=xray /usr/local/bin/xray /usr/local/bin/xray
COPY monitor.py report.py subserver.py /app/
ENTRYPOINT ["python3", "-u", "/app/monitor.py"]
