FROM ghcr.io/astral-sh/uv:0.13 AS uv

FROM docker.io/library/python:3.13-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg libchromaprint-tools \
  && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_PROJECT_ENVIRONMENT=/opt/venv \
  PATH=/opt/venv/bin:$PATH

WORKDIR /app

# Dependencies in their own layer, so a source change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# Owned by the runtime user, so a named volume mounted here inherits that
# ownership. Kubernetes can fix ownership with fsGroup; Compose cannot.
RUN mkdir /data && chown 1000:1000 /data

USER 1000:1000
EXPOSE 8000
CMD ["reelbarrow", "serve"]
