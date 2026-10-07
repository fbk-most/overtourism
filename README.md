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

This repository has separate Python environments for data preparation and for each backend. Clone the repository first:

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

## Dependencies

Each component's dependencies are defined in its own project file: [data preparation](pyproject.toml), [CRUD API](overtourism-backend/pyproject.toml), and [Model API](executor-backend/pyproject.toml). Running `uv sync --dev` in a component directory installs that project's dependencies into its `.venv`.

### Updating specific dependencies

Update a dependency in the project that declares it. Use the repository root for data preparation, `overtourism-backend` for the CRUD API, or `executor-backend` for the Model API:

```bash
uv sync --dev -P "${dependency}"
```

This updates only that project's environment.

## Usage

- [Data Preparation](./docs/howto/data.md)
- [Build and run Backend services](./docs/howto/backend.md)
- [Build and run Frontend application](./docs/howto/frontend.md)

## License

```
SPDX-License-Identifier: Apache-2.0
```
