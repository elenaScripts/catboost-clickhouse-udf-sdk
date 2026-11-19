"""Prepare a model bundle for clickhousectl local udf deploy."""
import argparse
import json
import shutil
from pathlib import Path
from zipfile import ZipFile

from chcatboost.bundle import build_bundle
from chcatboost.manifest import ModelManifest

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--model", type=Path, default=root / "dist/incident-risk.cbm")
parser.add_argument("--manifest", type=Path, default=root / "examples/incident-risk.manifest.json")
parser.add_argument("--output-dir", type=Path, default=root / "dist")
args = parser.parse_args()
manifest = ModelManifest.from_file(args.manifest)
archive = args.output_dir / "incident-risk-udf.zip"
build_bundle(args.model, args.manifest, archive)
target = args.output_dir / "local-udfs" / manifest.model_name
target.mkdir(parents=True, exist_ok=True)
with ZipFile(archive) as bundle:
    for name in ("main.py", "manifest.json", "model.cbm", "requirements.txt"):
        with bundle.open(name) as source, (target / name).open("wb") as destination:
            shutil.copyfileobj(source, destination)
config = {
    "functionName": manifest.model_name, "type": "executable_pool", "runtime": "python3.11",
    "arguments": [{"name": feature.name, "type": "Nullable(String)" if feature.type == "categorical" else "Nullable(Float64)"}
                  for feature in manifest.features],
    "returnType": "Float64", "format": "TabSeparated", "sendChunkHeader": True,
    "deterministic": True, "poolSize": 1,
}
(target / "udf.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
print(f"Prepared {target}")
