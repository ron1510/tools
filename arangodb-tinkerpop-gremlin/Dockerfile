ARG TINKERPOP_VERSION=3.8.1
ARG ARANGO_TINKERPOP_PROVIDER_VERSION=4.0.0

FROM eclipse-temurin:17-jre-jammy

ARG TINKERPOP_VERSION
ARG ARANGO_TINKERPOP_PROVIDER_VERSION

ENV GREMLIN_SERVER_HOME=/opt/gremlin-server
ENV GREMLIN_SERVER_PORT=8182

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl gettext-base unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://archive.apache.org/dist/tinkerpop/${TINKERPOP_VERSION}/apache-tinkerpop-gremlin-server-${TINKERPOP_VERSION}-bin.zip" -o /tmp/gremlin-server.zip \
    && unzip /tmp/gremlin-server.zip -d /opt \
    && mv "/opt/apache-tinkerpop-gremlin-server-${TINKERPOP_VERSION}" "${GREMLIN_SERVER_HOME}" \
    && rm /tmp/gremlin-server.zip

# Requires internet access or an internal Maven mirror during image build.
RUN "${GREMLIN_SERVER_HOME}/bin/gremlin-server.sh" install com.arangodb arangodb-tinkerpop-provider "${ARANGO_TINKERPOP_PROVIDER_VERSION}"

RUN groupadd --system --gid 10001 gremlin \
    && useradd --system --uid 10001 --gid gremlin --home-dir "${GREMLIN_SERVER_HOME}" --shell /usr/sbin/nologin gremlin \
    && mkdir -p "${GREMLIN_SERVER_HOME}/runtime-conf" "${GREMLIN_SERVER_HOME}/conf-templates" \
    && chown -R gremlin:gremlin "${GREMLIN_SERVER_HOME}"

COPY conf/ "${GREMLIN_SERVER_HOME}/conf-templates/"
COPY docker/entrypoint.sh /usr/local/bin/gremlin-entrypoint.sh

RUN chmod 0755 /usr/local/bin/gremlin-entrypoint.sh \
    && chown gremlin:gremlin /usr/local/bin/gremlin-entrypoint.sh

WORKDIR ${GREMLIN_SERVER_HOME}
USER 10001:10001

EXPOSE 8182

ENTRYPOINT ["/usr/local/bin/gremlin-entrypoint.sh"]
