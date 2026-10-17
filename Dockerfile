# --- build stage: compile dependencies (pyswisseph has no Linux wheel and needs a C compiler) ---
FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# The API serves ../frontend relative to backend/, so keep both directories side by side.
COPY backend /app/backend
COPY frontend /app/frontend

WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN uv sync --frozen --no-dev

# --- runtime stage: no compiler, non-root user ---
FROM python:3.12-slim

RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app:app /app /app
USER app

WORKDIR /app/backend
ENV PATH="/app/backend/.venv/bin:${PATH}"

EXPOSE 8000
# Hosting platforms (e.g. Render) pass the port in $PORT; default 8000 locally.
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
