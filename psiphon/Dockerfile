FROM debian:13-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl procps \
 && rm -rf /var/lib/apt/lists/*

# Same binary the host ran before the move to Docker.
COPY psiphon-tunnel-core /usr/local/bin/psiphon-tunnel-core
COPY healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod 755 /usr/local/bin/psiphon-tunnel-core /usr/local/bin/healthcheck.sh

ENTRYPOINT ["/usr/local/bin/psiphon-tunnel-core", "-config", "/etc/psiphon/client.config", "-dataRootDirectory", "/var/lib/psiphon"]
