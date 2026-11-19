import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "examples/train_scenario_model.py"
spec = importlib.util.spec_from_file_location("scenario", path)
scenario = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scenario)


def test_generated_period_is_repeatable_and_obeys_temporal_boundaries():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = scenario.generate_period(start, 7, 5000, 109, 100)
    assert first == scenario.generate_period(start, 7, 5000, 109, 100)
    features, labels, rows, metadata, windows = first
    times = [datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc) for row in rows]
    assert times == sorted(times)
    assert all(start <= t < start + timedelta(days=7) for t in times)
    assert {0, 1} == set(labels)
    assert sum(labels) == sum(metadata["incident_rows_by_type"].values())
    assert len({row[1] for row in rows}) == len(rows)
    assert all(5 <= row[4] <= 30_000 and 0 <= row[5] <= 4 for row in rows)
    assert any(x[1].startswith("5") and label == 0 for x, label in zip(features, labels))
    assert any(x[1] == "200" and label == 1 for x, label in zip(features, labels))
    assert sum(map(len, windows.values())) == metadata["windows"]


def test_threshold_metrics_are_row_level_and_handle_zero_denominators():
    assert scenario.threshold_metrics([1, 1, 0, 0], [0.8, 0.1, 0.7, 0.0], 0.5) == {
        "threshold": 0.5, "detected": 1, "missed": 1, "false_alarms": 1,
        "recall": 0.5, "precision": 0.5,
    }
    result = scenario.threshold_metrics([0, 0], [0.1, 0.2], 0.5)
    assert result["recall"] is None
    assert result["precision"] is None


def test_incident_detection_excludes_unobserved_windows():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    windows = {"checkout": [(start, start + timedelta(minutes=10), "errors"),
                            (start + timedelta(hours=1), start + timedelta(hours=2), "latency")]}
    rows = [["2026-01-01 00:02:00", 1, "checkout", "500", 500, 1, 1],
            ["2026-01-01 00:03:00", 2, "checkout", "500", 500, 1, 1],
            ["2026-01-01 00:30:00", 3, "checkout", "500", 500, 1, 0]]
    result = scenario.incident_metrics(rows, [0.1, 0.7, 0.8], windows, 0.5)
    assert result["incident_windows"] == 2
    assert result["observed_windows"] == 1
    assert result["detected_windows"] == 1
    assert result["median_detection_delay_seconds"] == 180
    assert result["flagged_normal_service_5min_buckets"] == 1
