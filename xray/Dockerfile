FROM alpine:3.20

ARG XRAY_VERSION=v26.10.21
ARG XRAY_SHA256=0eec3ed4163c273d8c8bf821f7d219e257921cf584aa3fb970715e458e631978

RUN apk add --no-cache ca-certificates tzdata \
 && apk add --no-cache --virtual .fetch curl unzip \
 && curl -fsSL -o /tmp/xray.zip "https://github.com/XTLS/Xray-core/releases/download/${XRAY_VERSION}/Xray-linux-64.zip" \
 && echo "${XRAY_SHA256}  /tmp/xray.zip" | sha256sum -c - \
 && mkdir -p /usr/local/share/xray \
 && unzip -q /tmp/xray.zip -d /tmp/xray \
 && install -m 755 /tmp/xray/xray /usr/local/bin/xray \
 && mv /tmp/xray/geoip.dat /tmp/xray/geosite.dat /usr/local/share/xray/ \
 && rm -rf /tmp/xray /tmp/xray.zip \
 && apk del .fetch

ENV XRAY_LOCATION_ASSET=/usr/local/share/xray
ENTRYPOINT ["/usr/local/bin/xray", "run", "-config", "/etc/xray/config.json"]
