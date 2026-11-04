#!/bin/sh
# Apply migrations, then serve.
#
# `init_db()` on lifespan calls SQLModel.metadata.create_all, which creates a
# table that is missing and does nothing to a table that already exists. That
# makes the migration history the only thing that can bring a deployed database
# up to date — and before this script existed, nothing ran it. Three model
# columns had been deployed-to-production-without existing for six weeks.
#
# Safe to run on every boot: `alembic upgrade head` is a no-op once at head.
# It is NOT safe to run concurrently from several replicas at once, so if this
# ever scales out, move it to a one-shot release job rather than the entrypoint.
set -e

echo "entrypoint: applying migrations"
alembic upgrade head

echo "entrypoint: starting api"
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --proxy-headers \
    --forwarded-allow-ips '*' \
    --timeout-keep-alive 65