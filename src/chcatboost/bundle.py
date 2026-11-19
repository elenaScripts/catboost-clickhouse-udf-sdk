"""Build a ClickHouse Cloud executable UDF archive."""

from __future__ import annotations

import importlib.metadata
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from .manifest import ModelManifest, load_and_validate_model


WORKER_PATH = Path(__file__).with_name("worker.py")


def build_bundle(model_path: str | Path, manifest_path: str | Path, output_path: str | Path) -> Path:
    model_file = Path(model_path).expanduser().resolve()
    manifest_file = Path(manifest_path).expanduser().resolve()
    output_file = Path(output_path).expanduser().resolve()

    if output_file in (model_file, manifest_file):
        raise ValueError("Output path must differ from the model and manifest paths")

    if not model_file.is_file():
        raise FileNotFoundError(f"Model file not found: {model_file}")
    if not manifest_file.is_file():
        raise FileNotFoundError(f"Manifest file not found: {manifest_file}")
    if model_file.suffix.lower() != ".cbm":
        raise ValueError("MVP accepts CatBoost binary model files with the .cbm extension")

    manifest = ModelManifest.from_file(manifest_file)
    load_and_validate_model(model_file, manifest)

    try:
        catboost_version = importlib.metadata.version("catboost")
    except importlib.metadata.PackageNotFoundError as exc:
        raise RuntimeError("Install CatBoost in the build environment before packaging") from exc

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="catboost-ch-udf-") as temp_dir:
        staging = Path(temp_dir)
        shutil.copyfile(model_file, staging / "model.cbm")
        shutil.copyfile(WORKER_PATH, staging / "main.py")
        (staging / "manifest.json").write_text(
            json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (staging / "requirements.txt").write_text(
            f"catboost=={catboost_version}\n", encoding="utf-8"
        )

        with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in ("main.py", "manifest.json", "model.cbm", "requirements.txt"):
                archive.write(staging / name, arcname=name)

    return output_file
