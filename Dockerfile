FROM python:3.12-bookworm

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the project into the image
ADD . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"
ENV AUTH_ENABLED=true
ENV AUTH_ISSUER=https://aac.platform.smartcommunitylab.it
ENV AUTH_JWKS_URL=https://aac.platform.smartcommunitylab.it/jwk
ENV AUTH_AUDIENCE=c_e550ec7f86174720872ac9c36fbecdcb
# ENV AUTH_TENANT_CLAIM=tenant_id
ENV AUTH_ALGORITHMS=RS256
ENV AUTH_LEEWAY_SECONDS=30


RUN useradd -m -u 8877 nonroot
RUN chown -R 8877:8877 /app
USER 8877

# Run the FastAPI application by default
# Uses `fastapi dev` to enable hot-reloading when the `watch` sync occurs
# Uses `--host 0.0.0.0` to allow access from outside the container
ENTRYPOINT ["fastapi", "run", "--host", "0.0.0.0", "/app/overtourism/overtourism/app_v2.py"]
