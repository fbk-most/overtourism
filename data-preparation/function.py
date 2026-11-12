import sys
from pathlib import Path


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    for source_dir in (project_dir, project_dir / "territorial_indexes"):
        source_path = str(source_dir)
        if source_path not in sys.path:
            sys.path.insert(0, source_path)

    from gen_phenomenon_dataframes import main_compute_all_dfs
    from model.common.config import setup_logging
    from model.fazzon.prepare import prepare as prepare_fazzon
    from model.molveno.prepare import prepare as prepare_molveno

    setup_logging()
    prepare_molveno(upload=True)
    prepare_fazzon(upload=True)
    main_compute_all_dfs(local=False, with_update=True)
