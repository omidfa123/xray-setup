FROM debian:13-slim

ARG LANTERN_VERSION=1.2.8
ARG LANTERN_SHA256=4a02d72b07727074c39ee46621a91800d12270e6c632211ec6cf240228fac1f6

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && curl -fsSL -o /tmp/l.tgz "https://github.com/getlantern/lantern-headless-client/releases/download/v${LANTERN_VERSION}/lantern-headless_${LANTERN_VERSION}_linux_amd64.tar.gz" \
 && echo "${LANTERN_SHA256}  /tmp/l.tgz" | sha256sum -c - \
 && tar -xzf /tmp/l.tgz -C /usr/local/bin lantern-headless \
 && chmod 755 /usr/local/bin/lantern-headless \
 && rm -f /tmp/l.tgz \
 && rm -rf /var/lib/apt/lists/*

ENTRYPOINT ["/usr/local/bin/lantern-headless", "--data-path", "/data", "start", \
            "--http-proxy-addr", "127.0.0.1:12345", "--socks-proxy-addr", "127.0.0.1:12346"]
