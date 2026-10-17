FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

RUN useradd --create-home --uid 10001 app
WORKDIR /app
# The API serves ../frontend relative to backend/, so keep both directories side by side.
COPY backend /app/backend
COPY frontend /app/frontend
RUN chown -R app:app /app
USER app

WORKDIR /app/backend
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/backend/.venv/bin:${PATH}"
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
