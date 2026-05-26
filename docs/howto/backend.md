# How to run overtouriusm backend

Here follows a brief guide on how to set up and run the overtourism backend.

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

Before deploying the FastAPI backend, log in into the digitalhub platform. To do so, you need the [CLI tool](https://github.com/scc-digitalhub/digitalhub-cli/releases). Pick an executable suitable for your operating system, unzip the archive.

Then launch the CLI tool and log in.

```bash
./dhcli register https://core.digitalhub-test.smartcommunitylab.it/
./dhcli login dhcore
```

Run the FastAPI backend with:

```bash
# You should already be inside the virtual environment and the right folder
fastapi run ./overtourism/overtourism/app_v1.py
```

## With Docker

You can build a container to run backend api:

```bash
docker build -t overtourism-backend .
docker run -it --rm -p 8000:8000 overtourism-backend
```

Or use a predefined container image `ghcr.io/tn-aixpa/overtourism-backend:latest`.

## With Platform

Define a container service function

```python
func = project.new_function(
    name="overtourism-backend",
    kind="container",
    image="ghcr.io/tn-aixpa/overtourism-backend:latest"
)
```

And run service function based on the above definition

```python
func.run(
    action="serve",
    service_ports=[{"port": 8000, "targetPort": 8000}]
)
```
