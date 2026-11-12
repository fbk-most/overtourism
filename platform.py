import os

import digitalhub as dh

def main():
    code = os.getenv("REPO_CODE", "./data-preparation")
    if code == "./data-preparation":
        handler = "function:main"
    else:
        handler = "data-preparation.function:main"

    project_name = os.getenv("PROJECT_NAME", "overtourism")
    project = dh.get_project(project_name)

    func = project.new_function(
        name="data-preparation",
        kind="python",
        python_version="PYTHON3_12",
        code_src=code,
        handler=handler,
        requirements=[
            "digitalhub==0.15.11",
            "odfpy",
            "openpyxl",
            "pyyaml",
            "unidecode",
            "geopandas",
            "pytest>=9.1.1",
            "matplotlib>=3.10.9",
            "scipy>=1.15.3",
            "scikit-learn>=1.7.2",
            "lxml>=6.1.3",
            "statsmodels>=0.15.0",
        ],
    )

    print("Building function...")
    func.run("build", wait=True)
    func.refresh()
    print("Function built successfully.")

    print("Running job...")
    func.run(
        "job",
        envs=[{"name": "PYTHONPATH", "value": "$PYTHONPATH:."}],
        volumes = [{
            "volume_type": "persistent_volume_claim",
            "name": "my-pvc",
            "mount_path": "/shared",
            "spec": {"size": "1Gi"},
        }],
        resources={"mem": "10Gi", "cpu": 4},
        wait=True,
    )
    print("Job completed successfully.")

if __name__ == "__main__":
    main()
