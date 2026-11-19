"""Worker program bundled into a ClickHouse executable_pool UDF."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from catboost import CatBoostClassifier, CatBoostRegressor, Pool


def _decode_tsv_row(line: str) -> list[str | None]:
    """Decode ClickHouse TabSeparated escaping for one physical input line."""
    # Detect the NULL marker before unescaping: the generic escape decoder
    # would otherwise turn ClickHouse's two-byte ``\\N`` marker into ``N``.
    raw_fields = line.rstrip("\r\n").split("\t")
    escapes = {"t": "\t", "n": "\n", "r": "\r", "0": "\0", "b": "\b", "f": "\f", "v": "\v", "\\": "\\"}

    def decode(value: str) -> str:
        output: list[str] = []
        index = 0
        while index < len(value):
            if value[index] == "\\" and index + 1 < len(value):
                index += 1
                output.append(escapes.get(value[index], value[index]))
            else:
                output.append(value[index])
            index += 1
        return "".join(output)

    return [None if value == "\\N" else decode(value) for value in raw_fields]


def _read_chunk(stream) -> list[list[str | None]] | None:
    header = stream.readline()
    if not header:
        return None
    try:
        row_count = int(header.decode("ascii").strip())
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError("Expected a decimal row-count chunk header") from exc
    if row_count < 0:
        raise ValueError("Chunk row count cannot be negative")

    rows = []
    for row_index in range(row_count):
        line = stream.readline()
        if not line:
            raise EOFError(f"Input ended after {row_index} of {row_count} rows")
        rows.append(_decode_tsv_row(line.decode("utf-8")))
    return rows


def _number_or_missing(value: str | None) -> float:
    if value is None:
        return math.nan
    return float(value)


def main() -> int:
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    features = manifest["features"]
    feature_names = [feature["name"] for feature in features]
    categorical_indices = [i for i, feature in enumerate(features) if feature["type"] == "categorical"]

    if manifest["task"] == "binary_classification":
        model = CatBoostClassifier()
        model.load_model(str(root / "model.cbm"), format="cbm")
        classes = list(model.classes_)
        positive_index = classes.index(manifest["positive_class"])
    else:
        model = CatBoostRegressor()
        model.load_model(str(root / "model.cbm"), format="cbm")
        positive_index = None

    source = sys.stdin.buffer
    sink = sys.stdout.buffer
    while True:
        rows = _read_chunk(source)
        if rows is None:
            return 0
        if not rows:
            sink.flush()
            continue

        expected_count = len(feature_names)
        for row_number, row in enumerate(rows):
            if len(row) != expected_count:
                raise ValueError(
                    f"Row {row_number} has {len(row)} values; expected {expected_count}"
                )

        data = []
        for row_number, row in enumerate(rows):
            converted = []
            for feature, value in zip(features, row, strict=True):
                if feature["type"] == "categorical":
                    if value is None:
                        raise ValueError(
                            f"Categorical feature {feature['name']!r} is NULL in row {row_number}"
                        )
                    converted.append(value)
                else:
                    converted.append(_number_or_missing(value))
            data.append(converted)

        pool = Pool(data, cat_features=categorical_indices, feature_names=feature_names)
        if manifest["task"] == "binary_classification":
            predictions = model.predict_proba(pool)[:, positive_index]
        else:
            predictions = model.predict(pool, prediction_type="RawFormulaVal")

        for prediction in predictions:
            value = float(prediction)
            if not math.isfinite(value):
                raise ValueError("Model produced a non-finite prediction")
            sink.write((format(value, ".17g") + "\n").encode("ascii"))
        sink.flush()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"catboost-clickhouse-udf: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
