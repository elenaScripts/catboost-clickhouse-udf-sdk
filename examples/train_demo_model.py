"""Train a reproducible demo model and write a ClickHouse-loadable TSV sample.

The generated incident label is synthetic. It demonstrates the integration
workflow; it is not a production model or a claim about real incident rates.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from catboost import CatBoostClassifier, Pool


FEATURE_NAMES = ["service", "error_code", "response_ms", "retry_count"]
CAT_FEATURES = [0, 1]
def make_dataset(count: int, seed: int, first_event_id: int):
    rng = random.Random(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    rows = []
    labels = []
    output_rows = []
    services = ("checkout", "search", "recommendations", "billing")
    service_weights = (0.32, 0.25, 0.20, 0.23)
    error_codes = ("200", "400", "404", "429", "500", "502", "503")
    error_weights = (0.62, 0.06, 0.08, 0.06, 0.08, 0.05, 0.05)

    for index in range(count):
        service = rng.choices(services, weights=service_weights, k=1)[0]
        error_code = rng.choices(error_codes, weights=error_weights, k=1)[0]
        response_ms = min(30_000, max(5, int(rng.lognormvariate(5.25, 0.85))))
        retry_count = rng.choices((0, 1, 2, 3, 4), weights=(0.72, 0.16, 0.07, 0.035, 0.015), k=1)[0]

        # Synthetic relationship: slow 5xx responses, retries, and a small
        # service-specific effect increase the probability of an incident.
        logit = -5.0
        if error_code.startswith("5"):
            logit += 1.5
        if response_ms > 1_500:
            logit += 1.25
        if response_ms > 5_000:
            logit += 0.8
        logit += 0.55 * retry_count
        if service == "checkout":
            logit += 0.45
        if error_code.startswith("5") and response_ms > 1_500:
            logit += 0.6

        probability = 1.0 / (1.0 + math.exp(-logit))
        incident = int(rng.random() < probability)
        features = [service, error_code, response_ms, retry_count]
        rows.append(features)
        labels.append(incident)
        timestamp = now - timedelta(seconds=rng.randrange(7 * 24 * 60 * 60))
        output_rows.append(
            [timestamp.strftime("%Y-%m-%d %H:%M:%S"), first_event_id + index, *features, incident]
        )

    return rows, labels, output_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--train-rows", type=int, default=30_000)
    parser.add_argument("--validation-rows", type=int, default=5_000)
    args = parser.parse_args()
    if args.train_rows < 100 or args.validation_rows < 100:
        parser.error("train-rows and validation-rows must each be at least 100")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    train_x, train_y, _ = make_dataset(args.train_rows, seed=41, first_event_id=1)
    valid_x, valid_y, valid_output = make_dataset(
        args.validation_rows, seed=73, first_event_id=1_000_000
    )
    train_pool = Pool(train_x, label=train_y, cat_features=CAT_FEATURES, feature_names=FEATURE_NAMES)
    valid_pool = Pool(valid_x, label=valid_y, cat_features=CAT_FEATURES, feature_names=FEATURE_NAMES)
    model = CatBoostClassifier(
        iterations=350,
        depth=6,
        learning_rate=0.08,
        loss_function="Logloss",
        eval_metric="AUC",
        random_seed=19,
        verbose=100,
        allow_writing_files=False,
    )
    model.fit(train_pool, eval_set=valid_pool, early_stopping_rounds=40)

    model_path = args.output_dir / "incident-risk.cbm"
    model.save_model(str(model_path), format="cbm")
    tsv_path = args.output_dir / "validation-logs.tsv"
    with tsv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerows(valid_output)

    best_scores = model.get_best_score().get("validation", {})
    print(f"Model: {model_path}")
    print(f"Validation rows: {tsv_path}")
    print(f"Synthetic validation incidents: {sum(valid_y)} / {len(valid_y)}")
    print(f"Validation AUC: {best_scores.get('AUC', 'not available')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
