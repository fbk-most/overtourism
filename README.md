# Overtourism Modeling

This repository contains code for modeling overtourism in
[Lake Molveno](https://en.wikipedia.org/wiki/Lake_Molveno) in
Italy. We develop this repository in the context of our R&D
activities at [Fondazione Bruno Kessler](https://www.fbk.eu/en/).

## Getting Started

The code is written in Python. We recommend using [uv](https://astral.sh/uv)
for managing the Python version, the virtual environment, and the
dependencies. Please, refer to `uv` documentation regarding how to
install it for your operating system.

This repository has separate Python environments for data preparation, each backend, and the database bootstrap utility. Clone the repository first:

```bash
git clone git@github.com/tn-aixpa/overtourism
cd overtourism
```

Run the setup for each component from the repository root, using a separate terminal for each environment:

```bash
# Data preparation (repository-level pyproject.toml)
uv sync --dev
source .venv/bin/activate
```

```bash
# CRUD API backend
cd overtourism-backend
uv sync --dev
source .venv/bin/activate
```

```bash
# Model API backend
cd executor-backend
uv sync --dev
source .venv/bin/activate
```

```bash
# Database schema and optional admin bootstrap
cd db-bootstrap
uv sync
source .venv/bin/activate
```

## Dependencies

Each component's dependencies are defined in its own project file: [data preparation](pyproject.toml), [CRUD API](overtourism-backend/pyproject.toml), [Model API](executor-backend/pyproject.toml), and [database bootstrap](db-bootstrap/pyproject.toml). Run `uv sync` in a component directory to install its dependencies into that project's `.venv`; use `--dev` for data preparation and the two backend projects.

### Updating specific dependencies

Update a dependency in the project that declares it. Use the repository root for data preparation, `overtourism-backend` for the CRUD API, `executor-backend` for the Model API, or `db-bootstrap` for the schema utility. For data preparation and the backend projects:

```bash
uv sync --dev -P "${dependency}"
```

For the bootstrap utility, run `uv sync -P "${dependency}"` from `db-bootstrap` (it has no development dependency group). Each command updates only that project's environment.

## Usage

- [Data Preparation](./docs/howto/data.md)
- [Build and run Backend services](./docs/howto/backend.md)
- [Build and run Frontend application](./docs/howto/frontend.md)

## License

```text
SPDX-License-Identifier: Apache-2.0
```
