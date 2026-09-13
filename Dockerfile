# NED runtime image.
#
# NED is offline by design: the container installs its dependencies at build
# time and makes no network calls at run time. It also runs as a non-root user
# and stores nothing.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1 \
    NED_HOST=0.0.0.0 \
    NED_PORT=8000

WORKDIR /app

# Dependencies first, so the layer is cached independently of the source.
COPY pyproject.toml README.md ./
COPY ned ./ned
RUN pip install --no-cache-dir .

# Run as a non-root user.
RUN useradd --create-home --shell /usr/sbin/nologin ned
USER ned

EXPOSE 8000

# No database, no volumes, no secrets: NED stores nothing about you.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["sh", "-c", "uvicorn ned.app.main:app --host ${NED_HOST} --port ${NED_PORT}"]
