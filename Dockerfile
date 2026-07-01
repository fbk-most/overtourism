FROM python:3.12-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image
ADD . /app

WORKDIR /app
RUN uv sync

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd -m -u 8877 nonroot
RUN chown -R 8877:8877 /app
USER 8877

# Run the FastAPI application by default
# Uses `fastapi dev` to enable hot-reloading when the `watch` sync occurs
# Uses `--host 0.0.0.0` to allow access from outside the container
ENTRYPOINT ["fastapi", "run", "--host", "0.0.0.0", "/app/overtourism/overtourism/app_v2.py"]
