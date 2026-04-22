FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Install production deps into .venv
RUN uv sync --frozen --no-dev

# Copy source
COPY src/ ./src/
COPY main.py ./

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

CMD ["python", "main.py"]
