# Run the synthetic incident scenario

This guide generates logs with service-specific latency, daily and weekly traffic patterns, and periods of service degradation. It then scores rows from a separate test period with an executable UDF. The generator also creates errors, retries, and slow responses outside incidents.

The parameters are illustrative. They are not estimates from production logs, and the scores do not establish real-world performance. The generator samples a fixed number of events per period, so its output does not estimate real request volume or alerts per hour.

## Prerequisites

Complete the installation steps in [Run the local demo](local-demo.md). The commands below use a local ClickHouse server named `demo` and the project's virtual environment.

## Generate the data and train the model

Run these commands from the project root:

```bash
source .venv/bin/activate
python examples/train_scenario_model.py --end-date 2026-11-19
python scripts/prepare_local_udf.py \
    --model dist/scenario/incident-risk.cbm \
    --manifest examples/incident-scenario.manifest.json \
    --output-dir dist/scenario
```

The end date is exclusive and uses UTC. Omit `--end-date` to use the current UTC date. The generator uses fixed seeds, so the same date and row counts produce the same data. CatBoost results may vary by environment. The model uses the first 14 days for training, the next three for early stopping, and the final seven for testing. `dist/scenario/metrics.json` records the periods, seeds, incident counts, AUC, and threshold metrics. `dist/scenario/test-logs.tsv` contains the test rows for ClickHouse. `dist/scenario/test-logs.csv` contains the same rows with a header and UTC timestamps. `dist/scenario/test-incidents.csv` contains the simulated incident windows.

## Load the test data

These steps use a server named `demo`. If needed, start it with the command in [the local demo](local-demo.md). The scenario uses its own UDF and table.

1. Deploy the model.

   ```bash
   export DO_NOT_TRACK=1
   clickhousectl local udf deploy incident_risk_scenario --server demo \
       --dir dist/scenario/local-udfs --python "$PWD/.venv/bin/python"
   ```

2. Create the table and load the test rows.

   ```bash
   clickhousectl local client demo --queries-file examples/create-incident-scenario.sql
   clickhousectl local client demo --query 'INSERT INTO incident_logs_scenario_utc FORMAT TabSeparated' < dist/scenario/test-logs.tsv
   clickhousectl local client demo --queries-file examples/create-incident-windows.sql
   clickhousectl local client demo --query "INSERT INTO incident_scenario_windows SETTINGS date_time_input_format = 'best_effort' FORMAT CSVWithNames" < dist/scenario/test-incidents.csv
   ```

   The create command fails if the table already exists. Use an empty table or a new server for a new test run. Do not insert the same file twice.

3. Compare thresholds.

   ```bash
   clickhousectl local client demo --queries-file examples/incident-scenario-evaluation.sql
   ```

   To inspect each observed incident window at threshold `0.10`, run:

   ```bash
   clickhousectl local client demo --queries-file examples/incident-window-evaluation.sql
   ```

   This query includes only windows with at least one sampled event. Both tables use UTC timestamps.

4. Compare the first 100 ClickHouse scores with direct CatBoost predictions.

   ```bash
   python scripts/verify_local.py --table incident_logs_scenario_utc --function incident_risk_scenario \
       --model dist/scenario/incident-risk.cbm --logs dist/scenario/test-logs.tsv
   ```

## Interpretation of the labels and metrics

A label of `1` means the row falls within a simulated incident window for its service. It does not mean that every request in the window failed. The four incident types change the distribution of latency and error codes by different amounts. Retries depend on each simulated request's error code and latency.

Row-level recall is the share of rows with label `1` that meet the threshold. Row-level precision is the share of rows meeting the threshold that have label `1`. Rows in an incident window are correlated, so these counts are not counts of independent incidents.

`incident_metrics` in `metrics.json` counts incident windows that have at least one sampled row. A window is detected when any of its rows meets the threshold. The detection delay is the time from the start of the window to its first flagged row. The report also counts five-minute service buckets with at least one flagged row outside an incident. A bucket can contain rows both inside and outside an incident. These buckets are a proxy for investigation volume, not a count of alerts from an alerting system. The sampled timestamps and one-row detection rule do not represent a measured production workload.

For a representative evaluation, calibrate the generator against consented or anonymized logs and a record of real incident intervals. Compare per-service traffic, latency distributions, error rates, retry behavior, and incident durations. Evaluate against a later period that the model and threshold selection did not use. Without those measurements, treat the scenario as an integration and sensitivity test.
