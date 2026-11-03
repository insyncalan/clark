# clark in a container (#427). Build from the top folder of the download (or of this repository):
#   docker compose -f docker/compose.yaml build
# Only clark's own files go in (the same list as the download, docker/Dockerfile.dockerignore): no tests, no tools, no data.
# The base image is pinned by its digest (python:3.12.12-slim-bookworm); changing it is a reviewed change, never an automatic one.
FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

# CLARK_CONTAINER=1 is what lets clark listen inside the container and trust the one peer a published port arrives from
# (src/clark/server.py, container_mode). It does nothing anywhere else. The compose file publishes the port to 127.0.0.1 only.
ENV CLARK_CONTAINER=1 \
    CLARK_PORT=8766 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# A user that is not root, and the folder the Mac's data folder is shared into.
RUN groupadd --gid 10001 clark \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin clark \
 && mkdir /data && chown clark:clark /data

WORKDIR /app
COPY clark/ ./clark/
COPY src/clark/ ./src/clark/
COPY vendor/README.md vendor/manifest.json ./vendor/
COPY vendor/et_xmlfile/ ./vendor/et_xmlfile/
COPY vendor/fonts/ ./vendor/fonts/
COPY vendor/licenses/ ./vendor/licenses/
COPY vendor/openpyxl/ ./vendor/openpyxl/

USER clark
EXPOSE 8766
VOLUME ["/data"]

# The page's own address check: /health answers {"ok": true} to the right Host, from inside the container.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python3", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8766/health', timeout=3).read()"]

CMD ["python3", "-m", "clark", "--data", "/data"]
