# The plan service's image, built from the repository's root:
#   docker build -f packages/hub-server/Dockerfile --build-arg VERSION=<version> .
# It installs basstler-hub-server at the versions uv.lock names, and reads its settings
# from the environment when it starts (see packages/hub-server/README.md).

FROM ghcr.io/astral-sh/uv:0.11.32 AS uv

FROM python:3.13-slim AS build
COPY --from=uv /uv /usr/local/bin/uv
# The release the image is of; the checkout copied in has no history to read it from.
ARG VERSION=0.0.0
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION} \
    UV_PROJECT_ENVIRONMENT=/opt/basstler \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /source
COPY . .
RUN uv sync --frozen --no-dev --no-editable --package basstler-hub-server

FROM python:3.13-slim
ARG VERSION=0.0.0
LABEL org.opencontainers.image.title="basstler-hub-server" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0"
COPY --from=build /opt/basstler /opt/basstler
ENV PATH=/opt/basstler/bin:${PATH} \
    PYTHONUNBUFFERED=1
USER nobody
EXPOSE 8080
CMD ["python", "-m", "basstler.hub_server", "serve"]
