FROM public.ecr.aws/docker/library/postgres:17-bookworm

ARG PGVECTOR_VERSION=0.8.1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        postgresql-server-dev-17 \
    && curl -fsSL "https://github.com/pgvector/pgvector/archive/refs/tags/v${PGVECTOR_VERSION}.tar.gz" \
        -o /tmp/pgvector.tar.gz \
    && tar -xzf /tmp/pgvector.tar.gz -C /tmp \
    && make -C "/tmp/pgvector-${PGVECTOR_VERSION}" \
    && make -C "/tmp/pgvector-${PGVECTOR_VERSION}" install \
    && rm -rf /tmp/pgvector* \
    && apt-get purge -y --auto-remove build-essential curl postgresql-server-dev-17 \
    && rm -rf /var/lib/apt/lists/*
