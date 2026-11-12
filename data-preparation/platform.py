import os

import digitalhub as dh


def main():
    project_name = os.getenv("PROJECT_NAME", "overtourism")
    project = dh.get_project(project_name)

    func = project.new_function(
        name="data-preparation",
        kind="python",
        python_version="PYTHON3_10",
        code_src="function.py",
        handler="main",
        requirements=[
            "numpy",
            "odfpy",
            "openpyxl",
            "pandas",
            "pyarrow",
            "pyyaml",
            "unidecode",
            "geopandas",
            "boto3>=1.43.110",
            "digitalhub==0.15.11",
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
    func.run("job", wait=True)
    print("Job completed successfully.")


if __name__ == "__main__":
    main()
