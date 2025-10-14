FROM public.ecr.aws/docker/library/python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PATH="/app/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=0
ENV UV_LINK_MODE=copy

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

COPY ./pyproject.toml ./uv.lock /app/
COPY . /app/sana

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

CMD ["python", "-m", "sana.main"]