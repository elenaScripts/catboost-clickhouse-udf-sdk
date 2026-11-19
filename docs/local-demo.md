# Run the local demo

In this tutorial, you will train a CatBoost classifier on synthetic service logs, run it as a local ClickHouse UDF, and compare its scores with direct CatBoost predictions.

The labels and data are synthetic. Do not use this model to make incident decisions. You need Python 3.11, an internet connection, and a terminal. The commands use macOS or Linux shell syntax. Run them from the project root.

## Install the tools

1. Create and activate a virtual environment.

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

2. Install the SDK and demo tools.

   ```bash
   python -m pip install -e '.[demo]'
   ```

3. Initialize the ClickHouse project.

   ```bash
   export DO_NOT_TRACK=1
   clickhousectl local init
   ```

   The command creates a project-specific `.clickhouse` directory. `DO_NOT_TRACK=1` disables clickhousectl telemetry for this shell.

## Train and package the model

1. Generate the synthetic data and train the classifier.

   ```bash
   python examples/train_demo_model.py --output-dir dist
   ```

   The output includes a validation AUC. The script writes `dist/incident-risk.cbm` and `dist/validation-logs.tsv`. Training results may vary with the environment.

2. Prepare the UDF files and ZIP.

   ```bash
   python scripts/prepare_local_udf.py
   ```

   The command writes `dist/incident-risk-udf.zip` and `dist/local-udfs/incident_risk/`.

## Start ClickHouse and deploy the UDF

1. Start a server named `demo`. The first start downloads ClickHouse. The specified ports must be free.

   ```bash
   clickhousectl local clickhouse start demo --version 26.10.6.18 --http-port 18123 --tcp-port 19000
   ```

2. Deploy the UDF using the Python interpreter from the virtual environment.

   ```bash
   clickhousectl local udf deploy incident_risk --server demo --dir dist/local-udfs --python "$PWD/.venv/bin/python"
   ```

3. Check that the server can call the UDF.

   ```bash
   clickhousectl local client demo --query "SELECT incident_risk(CAST('checkout', 'Nullable(String)'), CAST('500', 'Nullable(String)'), CAST(1600, 'Nullable(Float64)'), CAST(2, 'Nullable(Float64)'))"
   ```

   The query prints a numeric score between 0 and 1.

## Load and score the logs

These steps create `incident_logs` in the demo server's default database. If the table already exists, use the existing data or create a new server instead of loading the same rows twice.

1. Create the table.

   ```bash
   clickhousectl local client demo --queries-file examples/create-incident-logs.sql
   ```

2. Load the validation data.

   ```bash
   clickhousectl local client demo --query 'INSERT INTO incident_logs FORMAT TabSeparated' < dist/validation-logs.tsv
   ```

3. Run the ranking and threshold queries.

   ```bash
   clickhousectl local client demo --queries-file examples/incident-risk.sql
   ```

   The threshold query reports 5,000 scored events by default. The first query lists recent events in score order. The labels only measure the synthetic example.

4. Compare 100 SQL scores with direct CatBoost scores.

   ```bash
   python scripts/verify_local.py
   ```

   The script reports the maximum absolute difference and fails if it exceeds `1e-12`.

## Stop or restart the server

Stop the server when you have finished:

```bash
clickhousectl local clickhouse stop demo
```

To restart it, run `clickhousectl local clickhouse start demo`. The data and UDF remain in the project directory. If you retrain the model, run `scripts/prepare_local_udf.py` and deploy the UDF again. Create a new server or table before loading a newly generated validation file so the comparison uses matching rows.
