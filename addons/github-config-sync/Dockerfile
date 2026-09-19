ARG BUILD_FROM=ghcr.io/home-assistant/base:3.24-2026.08.0
FROM ${BUILD_FROM}

WORKDIR /app

COPY config.yaml /app/config.yaml
COPY rootfs /

ARG PREK_VERSION=v0.5.3
ARG TARGETARCH

RUN chmod a+x /usr/local/bin/start.sh \
    && apk add --no-cache python3 py3-flask py3-cryptography git curl ca-certificates \
    && case "${TARGETARCH}" in \
         amd64) PREK_ASSET="prek-x86_64-unknown-linux-musl.tar.gz" ;; \
         arm64) PREK_ASSET="prek-aarch64-unknown-linux-musl.tar.gz" ;; \
         *) echo "unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
       esac \
    && curl -fsSLo /tmp/prek.tar.gz \
         "https://github.com/j178/prek/releases/download/${PREK_VERSION}/${PREK_ASSET}" \
    && tar -xzf /tmp/prek.tar.gz -C /usr/local/bin --strip-components=1 \
    && rm /tmp/prek.tar.gz \
    && prek --version

EXPOSE 8099

CMD ["/usr/local/bin/start.sh"]
