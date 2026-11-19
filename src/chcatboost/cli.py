"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import sys

from catboost import CatBoostClassifier

from .bundle import build_bundle
from .manifest import ModelManifest, load_and_validate_model


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="catboost-ch",
        description="Package a CatBoost model as a ClickHouse executable Python UDF.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="Check a model against its feature manifest")
    inspect.add_argument("--model", required=True, help="Path to a CatBoost .cbm model")
    inspect.add_argument("--manifest", required=True, help="Path to the JSON feature manifest")

    build = commands.add_parser("build", help="Create a ClickHouse UDF ZIP bundle")
    build.add_argument("--model", required=True, help="Path to a CatBoost .cbm model")
    build.add_argument("--manifest", required=True, help="Path to the JSON feature manifest")
    build.add_argument("--output", required=True, help="Output ZIP path")

    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        manifest = ModelManifest.from_file(args.manifest)
        model = load_and_validate_model(args.model, manifest)
        if args.command == "inspect":
            signature = {
                "function_name": manifest.model_name,
                "arguments": [
                    {
                        "name": feature.name,
                        "type": (
                            "Nullable(String)"
                            if feature.type == "categorical"
                            else "Nullable(Float64)"
                        ),
                    }
                    for feature in manifest.features
                ],
                "return_type": "Float64",
                "udf_type": "executable_pool",
                "runtime": "python3.11",
                "format": "TabSeparated",
                "send_chunk_header": True,
                "deterministic": True,
                "task": manifest.task,
                "model_version": manifest.version,
            }
            print(json.dumps(signature, indent=2, ensure_ascii=False))
            return 0

        output = build_bundle(args.model, args.manifest, args.output)
        print(f"Created {output}")
        print("Deploy as an executable_pool Python 3.11 UDF with TabSeparated format.")
        print("Enable send_chunk_header; start with a small pool and tune after measuring.")
        print("Model classes: " + ", ".join(map(str, model.classes_)) if isinstance(model, CatBoostClassifier) else "Model type: regression")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
