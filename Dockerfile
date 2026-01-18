FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
EXPOSE 9000

CMD ["sh", "-c", "uv run src/main.py & mkdocs serve -f mkdocs.yml -w ./docs --no-strict -a 0.0.0.0:9000" ]

