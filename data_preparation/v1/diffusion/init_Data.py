import os
import sys
from pathlib import Path

from data_preparation.utils import get_s3, BASE_DIR

def mk_dir(dir: Path):
    Path.mkdir(dir, exist_ok = True)

def get_file(path: Path, name: str, s3_dir: str = None):
    if not (path / name).exists():
        with open(path / name, "wb") as f:
            f.write(get_s3(name if s3_dir is None else s3_dir + "/" + name).getvalue())

def init_Data():
    PATH_TO_DATA = Path(BASE_DIR) / "Data"
    mk_dir(PATH_TO_DATA)

    get_file(PATH_TO_DATA, "POSAS_2024_it_022_Trento.csv")

    ZONING_PATH = "mavfa-fbk_AIxPA_tourism-delivery_2025.08.22-zoning"
    PATH_TO_ZONING = PATH_TO_DATA / ZONING_PATH
    mk_dir(PATH_TO_ZONING)

    for suffix in [".cpg", ".dbf", ".prj", ".qmd", ".shp", ".shx"]:
        get_file(PATH_TO_ZONING, "fbk-aixpa-turismo" + suffix, s3_dir=ZONING_PATH)

if __name__ == "__main__":
    init_Data()