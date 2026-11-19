"""Train and evaluate a model on synthetic service incidents in separate periods."""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from catboost import CatBoostClassifier, Pool

FEATURE_NAMES = ["service", "error_code", "response_ms", "retry_count"]
SERVICES = ("checkout", "search", "recommendations", "billing")
SERVICE_WEIGHTS = (0.32, 0.30, 0.22, 0.16)
BASE_LATENCY = {"checkout": 220, "search": 140, "recommendations": 280, "billing": 190}
# These are illustrative assumptions, not estimates from measured production logs.
INCIDENT_TYPES = {
    "latency": (1.9, 0.07),
    "errors": (1.25, 0.24),
    "overload": (2.4, 0.17),
    "subtle": (1.25, 0.025),
}


def generate_period(start: datetime, days: int, count: int, seed: int, first_id: int):
    """Generate incident windows and events. Each label marks an active service incident."""
    rng = random.Random(seed)
    windows = {service: [] for service in SERVICES}
    for day in range(days):
        for service in SERVICES:
            if rng.random() < 0.70:
                beginning = start + timedelta(days=day, minutes=rng.randint(0, 21 * 60))
                end = beginning + timedelta(minutes=rng.randint(40, 150))
                kind = rng.choice(tuple(INCIDENT_TYPES))
                windows[service].append((beginning, end, kind))

    timestamps = []
    while len(timestamps) < count:
        timestamp = start + timedelta(seconds=rng.randrange(days * 86400))
        # Traffic peaks during daytime and falls overnight and on weekends.
        hour = timestamp.hour + timestamp.minute / 60
        day_factor = 0.75 if timestamp.weekday() >= 5 else 1.0
        traffic = day_factor * (0.60 + 0.40 * math.cos((hour - 14) * math.pi / 12))
        if rng.random() < traffic:
            timestamps.append(timestamp)
    timestamps.sort()

    features, labels, rows = [], [], []
    kind_counts = {kind: 0 for kind in INCIDENT_TYPES}
    for index, timestamp in enumerate(timestamps):
        service = rng.choices(SERVICES, weights=SERVICE_WEIGHTS, k=1)[0]
        kind = next((name for beginning, end, name in windows[service] if beginning <= timestamp < end), None)
        is_incident = int(kind is not None)
        multiplier, extra_error = INCIDENT_TYPES[kind] if kind else (1.0, 0.0)
        if kind:
            kind_counts[kind] += 1
        # Individual requests remain noisy: 5xx errors and slow requests also occur outside incidents.
        code_draw = rng.random()
        if code_draw < 0.018 + extra_error:
            code = rng.choices(("500", "502", "503", "504"), weights=(4, 2, 3, 1))[0]
        elif code_draw < 0.095 + extra_error:
            code = rng.choices(("400", "404", "429"), weights=(4, 3, 2))[0]
        else:
            code = "200"
        daytime_load = 1.0 + 0.18 * math.cos((timestamp.hour - 14) * math.pi / 12)
        error_factor = 1.35 if code.startswith("5") or code == "429" else 1.0
        response = max(5, min(30_000, round(rng.lognormvariate(
            math.log(BASE_LATENCY[service] * multiplier * daytime_load * error_factor), 0.8))))
        retry_probability = 0.015 + (0.24 if code.startswith("5") or code == "429" else 0.0)
        if response > 1200:
            retry_probability += 0.12
        retries = min(4, sum(rng.random() < retry_probability for _ in range(4)))
        feature = [service, code, response, retries]
        features.append(feature)
        labels.append(is_incident)
        rows.append([timestamp.strftime("%Y-%m-%d %H:%M:%S"), first_id + index, *feature, is_incident])
    return features, labels, rows, {"windows": sum(map(len, windows.values())), "incident_rows_by_type": kind_counts}, windows


def threshold_metrics(labels, scores, threshold):
    tp = sum(bool(score >= threshold and label == 1) for label, score in zip(labels, scores, strict=True))
    fp = sum(bool(score >= threshold and label == 0) for label, score in zip(labels, scores, strict=True))
    fn = sum(bool(score < threshold and label == 1) for label, score in zip(labels, scores, strict=True))
    return {"threshold": threshold, "detected": tp, "missed": fn, "false_alarms": fp,
            "recall": tp / (tp + fn) if tp + fn else None,
            "precision": tp / (tp + fp) if tp + fp else None}


def incident_metrics(rows, scores, windows, threshold):
    """Count incident windows with an observed and then a flagged event."""
    events = {service: [] for service in SERVICES}
    flagged_normal_buckets = set()
    for row, score in zip(rows, scores, strict=True):
        timestamp = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        events[row[2]].append((timestamp, float(score)))
        if row[6] == 0 and score >= threshold:
            flagged_normal_buckets.add((row[2], int(timestamp.timestamp()) // 300))
    observed = detected = 0
    delays = []
    for service, intervals in windows.items():
        for beginning, end, _ in intervals:
            inside = [(timestamp, score) for timestamp, score in events[service] if beginning <= timestamp < end]
            if not inside:
                continue
            observed += 1
            flagged = [timestamp for timestamp, score in inside if score >= threshold]
            if flagged:
                detected += 1
                delays.append((min(flagged) - beginning).total_seconds())
    return {"threshold": threshold, "incident_windows": sum(map(len, windows.values())),
            "observed_windows": observed, "detected_windows": detected,
            "median_detection_delay_seconds": statistics.median(delays) if delays else None,
            "flagged_normal_service_5min_buckets": len(flagged_normal_buckets)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist/scenario"))
    parser.add_argument("--end-date", type=datetime.fromisoformat,
                        help="Exclusive UTC end date, YYYY-MM-DD (default: today at 00:00 UTC)")
    parser.add_argument("--train-rows", type=int, default=30_000)
    parser.add_argument("--validation-rows", type=int, default=8_000)
    parser.add_argument("--test-rows", type=int, default=10_000)
    args = parser.parse_args()
    if min(args.train_rows, args.validation_rows, args.test_rows) < 100:
        parser.error("Each period requires at least 100 rows")
    if args.end_date is not None and (args.end_date.tzinfo is not None or args.end_date.time() != time.min):
        parser.error("--end-date must be a date in YYYY-MM-DD format")
    end = (args.end_date or datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)).replace(tzinfo=timezone.utc)
    specifications = [("train", end - timedelta(days=24), 14, args.train_rows, 41, 1),
                      ("validation", end - timedelta(days=10), 3, args.validation_rows, 73, 1_000_000),
                      ("test", end - timedelta(days=7), 7, args.test_rows, 109, 2_000_000)]
    periods = {name: generate_period(start, days, count, seed, first_id)
               for name, start, days, count, seed, first_id in specifications}
    if any(len(set(periods[name][1])) != 2 for name in periods):
        parser.error("A period contains only one class. Increase the row counts or change the end date.")
    pools = {name: Pool(x, label=y, cat_features=[0, 1], feature_names=FEATURE_NAMES)
             for name, (x, y, _, _, _) in periods.items()}
    model = CatBoostClassifier(iterations=350, depth=6, learning_rate=0.08, loss_function="Logloss",
                               eval_metric="AUC", random_seed=19, verbose=100, allow_writing_files=False)
    model.fit(pools["train"], eval_set=pools["validation"], early_stopping_rounds=40)
    scores = model.predict_proba(pools["test"])[:, list(model.classes_).index(1)]
    auc = model.eval_metrics(pools["test"], ["AUC"])["AUC"][-1]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model.save_model(str(args.output_dir / "incident-risk.cbm"))
    with (args.output_dir / "test-logs.tsv").open("w", encoding="utf-8", newline="") as stream:
        csv.writer(stream, delimiter="\t", lineterminator="\n").writerows(periods["test"][2])
    with (args.output_dir / "test-logs.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("event_time_utc", "event_id", "service", "error_code", "response_ms", "retry_count", "incident"))
        for row in periods["test"][2]:
            writer.writerow([row[0].replace(" ", "T") + "Z", *row[1:]])
    with (args.output_dir / "test-incidents.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(("service", "start_utc", "end_utc", "simulated_type"))
        for service, intervals in periods["test"][4].items():
            for beginning, finish, kind in intervals:
                writer.writerow((service, beginning.isoformat(), finish.isoformat(), kind))
    summary = {"description": "Simulated service incidents; not calibrated to real logs",
               "label": "1 when an event occurs during a simulated incident for its service",
               "periods": {name: {"start_utc": start.isoformat(), "end_utc": (start + timedelta(days=days)).isoformat(),
                                  "rows": count, "incident_rows": sum(periods[name][1]), "seed": seed, **periods[name][3]}
                           for name, start, days, count, seed, _ in specifications},
               "test_auc": auc,
               "thresholds": [threshold_metrics(periods["test"][1], scores, threshold)
                              for threshold in (0.01, 0.02, 0.05, 0.10, 0.20)],
               "incident_metrics": [incident_metrics(periods["test"][2], scores, periods["test"][4], threshold)
                                    for threshold in (0.01, 0.02, 0.05, 0.10, 0.20)]}
    (args.output_dir / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
