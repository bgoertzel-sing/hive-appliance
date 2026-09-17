# ---- Omega Hive Appliance ----
# Multi-stage build: build wheel, then install into slim runtime image.

# -- Stage 1: Build --
FROM python:3.11-slim AS builder

WORKDIR /build
COPY . .

RUN pip install --no-cache-dir build \
 && python -m build --wheel --outdir /dist

# -- Stage 2: Runtime --
FROM python:3.11-slim

LABEL maintainer="Omega Hive Team"
LABEL description="Omega Hive Appliance — managed hive observation, diagnosis, and repair"

# Create non-root user
RUN groupadd -r hive && useradd -r -g hive -d /app hive

WORKDIR /app

# Install the built wheel (no external deps for core)
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# Default state directory
ENV HIVE_STORE_PATH=/app/state/events.db
RUN mkdir -p /app/state && chown -R hive:hive /app

USER hive

ENTRYPOINT ["hive-appliance"]
CMD ["--help"]
