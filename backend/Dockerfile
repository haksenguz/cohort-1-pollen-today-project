# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Installed from the pinned image rather than `pip install uv`, so the build does
# not depend on whatever uv happens to be on PyPI that day.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

# Dependencies resolve from uv.lock, not from a hand-written list. The previous
# version of this file pip-installed five packages by name and shipped none of
# langgraph, pyjwt, pwdlib, openai, alembic, apscheduler or greenlet - an image
# that could not import the agent or authenticate anybody.
#
# --no-install-project on purpose: this project has no build backend, and it does
# not need to be installed to run. `uvicorn app.main:app` imports it from /app.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY db ./db
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts

# Unprivileged. Nothing in the app writes to disk.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

# --proxy-headers is required, not cosmetic: the rate limiter keys on the client
# IP, and behind nginx or a PaaS proxy every request would otherwise appear to
# come from the proxy and share one bucket.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*", \
     "--timeout-keep-alive", "65"]