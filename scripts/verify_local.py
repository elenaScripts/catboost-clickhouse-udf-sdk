"""Compare ClickHouse UDF scores with CatBoost on the first 100 demo rows."""
import argparse
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

from catboost import CatBoostClassifier, Pool

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--server", default="demo")
parser.add_argument("--table", default="incident_logs")
parser.add_argument("--function", default="incident_risk")
parser.add_argument("--model", type=Path, default=root / "dist/incident-risk.cbm")
parser.add_argument("--logs", type=Path, default=root / "dist/validation-logs.tsv")
args = parser.parse_args()
if not all(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in (args.table, args.function)):
    parser.error("Table and function must be unqualified SQL identifiers")
ctl = Path(sys.executable).parent / "clickhousectl"
query = f"""SELECT event_id, {args.function}(
    CAST(service, 'Nullable(String)'), CAST(error_code, 'Nullable(String)'),
    CAST(response_ms, 'Nullable(Float64)'), CAST(retry_count, 'Nullable(Float64)'))
    FROM {args.table} ORDER BY event_id LIMIT 100 FORMAT TabSeparated"""
env = dict(os.environ, DO_NOT_TRACK="1")
result = subprocess.run([str(ctl), "local", "client", args.server, "--query", query],
                        cwd=root, env=env, text=True, capture_output=True, check=True)
scores = {int(event_id): float(score) for event_id, score in csv.reader(result.stdout.splitlines(), delimiter="\t")}
with args.logs.open(encoding="utf-8", newline="") as stream:
    rows = list(csv.reader(stream, delimiter="\t"))
selected = [row for row in rows if int(row[1]) in scores]
if len(scores) != 100 or len(selected) != 100:
    raise SystemExit("Expected 100 matching rows in ClickHouse and the TSV file")
model = CatBoostClassifier()
model.load_model(str(args.model))
data = [[row[2], row[3], float(row[4]), float(row[5])] for row in selected]
pool = Pool(data, cat_features=[0, 1], feature_names=["service", "error_code", "response_ms", "retry_count"])
predictions = model.predict_proba(pool)[:, list(model.classes_).index(1)]
max_diff = max(abs(float(prediction) - scores[int(row[1])]) for row, prediction in zip(selected, predictions, strict=True))
print(f"Compared {len(selected)} rows. Maximum absolute difference: {max_diff:.3g}")
if max_diff > 1e-12:
    raise SystemExit("ClickHouse and direct CatBoost predictions differ")
