# Overtourism Backend

The backend runs as two separate services:

| Service | Project | Responsibility | Port |
| --- | --- | --- | --- |
| CRUD API | `overtourism-backend` | Manages users, territories, problems, scenarios, and evaluations. | `8000` |
| Model API | `executor-backend` | Lists and evaluates the Fazzon and Molveno models. | `8001` |

The CRUD API calls the Model API over HTTP. Start the Model API first: the CRUD application reads its model registry during startup and its readiness check also depends on the Model API. Expose the CRUD API to clients; keep the Model API on a private network because it does not validate end-user JWTs.

## Configuration

Backend requires the datasets and artefacts to build a Digital Twin model on startup.
The data may be either provided manually (standalone mode) or may be downloaded from the platform.

To enable standalone mode, run the application with the following configuration:

- `DT_OVERTURISM_STANDALONE_MODE` environment variable set to true. Ensure that the datasets are available on startup (see below)

The data is expected to be found at the `data/index_data` folder relative to the working directory. To change the default location,
use `DT_OVERTURISM_INDEX_DATA_PATH` environment variable.

Note that when the backend is run in a non standalone mode, the platform credentials should be available (via environment or CLI setup). It is also
necessary to specify the project from which the data items and artefacts should be downloaded. The name of the project is defined with
`PROJECT_NAME` variable.

## Local execution

When running outside standalone mode, the CRUD API needs credentials to download data from the DigitalHub platform. This platform login is separate from end-user authentication. Install the [DigitalHub CLI](https://github.com/scc-digitalhub/digitalhub-cli/releases), then register and log in:

```bash
./dhcli register https://core.digitalhub-test.smartcommunitylab.it/
./dhcli login dhcore
```

Run the services in separate terminals from the repository root. Start the Model API first:

```bash
cd executor-backend
uv sync
source .venv/bin/activate
fastapi run --host 127.0.0.1 --port 8001 src/api/main.py
```

Wait for the Model API readiness probe to return `200`, then start the CRUD API in another terminal:

```bash
curl --fail http://127.0.0.1:8001/health/ready
```

```bash
cd overtourism-backend
uv sync
source .venv/bin/activate
MODEL_BACKEND_URL=http://127.0.0.1:8001 fastapi run --host 127.0.0.1 --port 8000 overtourism/overtourism/app.py
```

## Authentication flow

The CRUD API does not provide a login page or authenticate user credentials. An external identity provider authenticates the user and issues a JWT access token. The frontend sends it to the CRUD API as `Authorization: Bearer <token>`; it does not send the user's token to the Model API.

With `AUTH_ENABLED=true`, the CRUD API verifies the token signature using the identity provider's JWKS, checks the issuer and audience, and uses the `sub` claim to identify the user. The user's active status, role, and territory assignments are read from the backend database; territory claims in the token do not grant access. The first admin must be provisioned in that database, and users are linked to their identity-provider subject on their first request using a matching, verified email. See [Authentication setup](auth.md) for admin provisioning and authorization details.

## Environment variables

Set `CORS_ALLOWED_ORIGINS` on both API processes. Set the other variables on the CRUD API unless otherwise noted. Origins are comma-separated full browser origins, including scheme and port when applicable, for example `https://app.example.com,http://localhost:5173`. If unset, the default is `*`; configure an explicit list for deployment. Authentication is disabled by default, so enable and configure it before exposing the CRUD API beyond local development.

| Variable | Required when | Default / purpose |
| --- | --- | --- |
| `CORS_ALLOWED_ORIGINS` | Optional; set on both APIs for deployment. | Comma-separated allowed origins; defaults to `*`. |
| `AUTH_ENABLED` | Always choose explicitly for deployment. | `false`; set to `true` to validate bearer tokens. |
| `AUTH_JWKS_URL` | `AUTH_ENABLED=true` | Identity provider's JWKS endpoint. |
| `AUTH_ISSUER` | `AUTH_ENABLED=true` | Expected JWT issuer. |
| `AUTH_AUDIENCE` | `AUTH_ENABLED=true` | Expected JWT audience. |
| `AUTH_ALGORITHMS` | Optional | Accepted JWT algorithms; defaults to `RS256`. |
| `AUTH_LEEWAY_SECONDS` | Optional | JWT clock-skew allowance; defaults to `30` seconds. |
| `MODEL_BACKEND_URL` | When the Model API is not at the local default. | Defaults to `http://localhost:8001`; for containers, use the Model API's private service address. |
| `OVERTOURISM_DATABASE` | Optional locally; set to a persistent database in deployment. | SQLAlchemy database URL; defaults to a SQLite file under `overtourism/overtourism/database/`. |
| `MODEL_BACKEND_USER`, `MODEL_BACKEND_PASSWORD` | Only if an upstream proxy requires HTTP Basic authentication. | The CRUD API sends Basic credentials only when both are set. The Model API itself does not validate them. |

The data-related settings `DT_OVERTURISM_STANDALONE_MODE` and `PROJECT_NAME` are described in [Configuration](#configuration).

## Health probes

Both services expose unauthenticated operational probes:

- `GET /health/live` returns `200` while the process can answer requests. It does not check external dependencies.
- `GET /health/ready` returns `200` when ready, or `503` otherwise. The CRUD API checks its SQL store with `SELECT 1` and the Model API's readiness. The Model API checks that its model registry is available and consistent.

## With Docker

Build and run the Model API on a private Docker network:

```bash
docker network create overtourism

cd executor-backend
docker build -f Dockerfile.model -t overtourism-model .
docker run -d --rm --name overtourism-model --network overtourism \
    -p 127.0.0.1:8001:8001 \
    -e CORS_ALLOWED_ORIGINS \
    overtourism-model
```

Wait for `curl --fail http://127.0.0.1:8001/health/ready` to return `200`. In another terminal, from the repository root, build and run the CRUD API. Export `CORS_ALLOWED_ORIGINS`, the OIDC variables, and a persistent `OVERTOURISM_DATABASE` URL before starting it:

```bash
cd overtourism-backend
docker build -f Dockerfile.crud -t overtourism-crud .
docker run -d --rm --name overtourism-crud --network overtourism -p 8000:8000 \
    -e CORS_ALLOWED_ORIGINS \
    -e MODEL_BACKEND_URL=http://overtourism-model:8001 \
    -e AUTH_ENABLED=true \
    -e AUTH_JWKS_URL \
    -e AUTH_ISSUER \
    -e AUTH_AUDIENCE \
    -e OVERTOURISM_DATABASE \
    overtourism-crud
```

`OVERTOURISM_DATABASE` should point to a persistent database for deployment. The model container is not published to the host; the CRUD API reaches it through the Docker network.
