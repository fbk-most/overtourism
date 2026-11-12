# SPDX-License-Identifier: Apache-2.0
"""Data files of a model: location, download from the platform, startup check.

A model whose statistics come from a data-preparation pipeline (logged to the DigitalHub
platform as dataitems with ``--upload``) reads them from its data folder:

* the model's environment variable (e.g. ``FAZZON_DATA_DIR``), if set;
* otherwise ``<executor-backend>/database/<model>``.

As for the indicator data of the CRUD API (``download_index_data``), the same environment
variables select where the data comes from:

* ``DT_OVERTURISM_STANDALONE_MODE`` (default ``true``): in standalone mode nothing is
  downloaded and the files must already be in the folder;
* ``PROJECT_NAME`` (default ``overtourism``): the platform project of the dataitems;
  platform credentials come from the environment or a ``dhcli login``.

Unlike the indicator data, any failure raises: a model without its data does not start.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_DIR = Path(os.getenv("DT_MODEL_DATABASE_DIR", Path(__file__).resolve().parents[3] / "database"))


def standalone_mode() -> bool:
    return os.getenv("DT_OVERTURISM_STANDALONE_MODE", "true").lower() == "true"


@dataclass(frozen=True)
class ModelData:
    """The data files of one model.

    *validate* is called on a folder holding freshly downloaded files and raises if they
    cannot be used by the model.
    """

    model: str
    files: tuple[str, ...]
    env_var: str
    validate: Callable[[Path], None]

    @property
    def default_dir(self) -> Path:
        return DATABASE_DIR / self.model

    def data_dir(self) -> Path:
        """Folder of the data files (the environment variable or the default)."""
        return Path(os.environ.get(self.env_var) or self.default_dir)

    def missing_files(self, folder: Path) -> list[str]:
        return [name for name in self.files if not (folder / name).exists()]

    def download(self, overwrite: bool = False) -> Path:
        """Download the dataitems from the platform into :meth:`data_dir`.

        Without *overwrite*, nothing is downloaded if all the files are already there.
        The files are downloaded to a temporary folder and validated; only then they
        replace the current ones.  Any failure raises and leaves the current files
        untouched.
        """
        target = self.data_dir()
        if not overwrite and not self.missing_files(target):
            logger.info("%s data already in %s: download skipped", self.model, target)
            return target

        import digitalhub as dh  # type: ignore[import-untyped]

        project_name = os.getenv("PROJECT_NAME", "overtourism")
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=target.parent, prefix=f".{self.model}_download_"
        ) as tmp:
            tmp_dir = Path(tmp)
            try:
                project = dh.get_project(project_name)
                for name in self.files:
                    logger.info(
                        "Downloading dataitem %s from project %s", name, project_name
                    )
                    project.get_dataitem(name).download(str(tmp_dir), overwrite=True)
            except Exception as e:
                raise RuntimeError(
                    f"{self.model} data download from platform project {project_name!r} failed: {e}"
                ) from e
            missing = self.missing_files(tmp_dir)
            if missing:
                raise RuntimeError(
                    f"{self.model} data download: files not received {missing}"
                )
            self.validate(tmp_dir)  # raise if the new files are not usable
            for name in self.files:
                shutil.move(str(tmp_dir / name), str(target / name))
        logger.info("%s data downloaded to %s", self.model, target)
        return target

    def ensure(self) -> Path:
        """Startup step: download the data unless in standalone mode, then check it is there."""
        if not standalone_mode():
            self.download()
        target = self.data_dir()
        missing = self.missing_files(target)
        if missing:
            raise FileNotFoundError(
                f"{self.model} data files missing in {target}: {missing} "
                f"(set {self.env_var}, or DT_OVERTURISM_STANDALONE_MODE=false to download them)"
            )
        return target
