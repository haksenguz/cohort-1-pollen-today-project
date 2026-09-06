FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
RUN uv pip install --system --no-cache \
    "fastapi[standard]>=0.115" "sqlmodel>=0.0.22" "asyncpg>=0.29" \
    "pydantic-settings>=2.4" "httpx>=0.27"

COPY app ./app

EXPOSE 8000
CMD ["fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8000"]
