FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install uv

COPY pyproject.toml uv.lock* ./

ENV UV_PROJECT_ENVIRONMENT=/tmp/.venv

RUN uv sync --frozen --no-dev

COPY . .

CMD ["uv", "run", "python", "-m", "src.main"]
