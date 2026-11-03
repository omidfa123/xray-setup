FROM alpine:3.20

ARG HY2_VERSION=v2.13.0
ARG HY2_SHA256=907ba8c9693edb104b20582681fb7dc15639d5b64a9cbb616a7b539190a86691

RUN apk add --no-cache ca-certificates tzdata \
 && apk add --no-cache --virtual .fetch curl \
 && curl -fsSL -o /usr/local/bin/hysteria "https://github.com/apernet/hysteria/releases/download/app%2F${HY2_VERSION}/hysteria-linux-amd64" \
 && echo "${HY2_SHA256}  /usr/local/bin/hysteria" | sha256sum -c - \
 && chmod 755 /usr/local/bin/hysteria \
 && apk del .fetch

ENTRYPOINT ["/usr/local/bin/hysteria", "server", "--disable-update-check", "-c", "/etc/hysteria/config.yaml"]
