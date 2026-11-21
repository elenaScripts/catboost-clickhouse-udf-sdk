# Score log events from a file

This optional tutorial reads synthetic JSON log events with ClickHouse FileLog and scores them with the sample `incident_risk` UDF.

```text
app.log → FileLog → materialized view → MergeTree table → SQL + incident_risk
```

FileLog runs on the ClickHouse server and reads files accessible to that server. This example uses a local server, not ClickHouse Cloud. The data and model are synthetic; the scores are not real incident probabilities.

## Prerequisites

Complete [Start ClickHouse and deploy the UDF](local-demo.md#start-clickhouse-and-deploy-the-udf) in the local demo first. The commands below use its `demo` server, Python environment, and `incident_risk` function. Run them from the project root.

The FileLog glob in this tutorial requires ClickHouse 26.10 or later. The demo was tested with ClickHouse 26.10.6.18 and `clickhousectl` 0.6.0 on macOS ARM64.

## Set up the log source

These commands create a directory under the local server's `user_files` directory and three database objects: `filelog_source`, `filelog_events`, and `filelog_to_events`. Use a fresh demo server if these names or the `incident-filelog` directory already exist. Do not use this example to modify production logs or tables.

1. Create an empty log file. The directory and file must exist before you create the FileLog table.

   ```bash
   mkdir -p .clickhouse/servers/demo/data/user_files/incident-filelog
   touch .clickhouse/servers/demo/data/user_files/incident-filelog/app.log
   ```

2. Create the FileLog source, a MergeTree table for the events, and a materialized view that copies new events into that table:

   ```bash
   clickhousectl local client demo --queries-file examples/create-filelog-demo.sql
   ```

   The source watches `incident-filelog/*.log`, relative to the server's `user_files` directory. The materialized view starts background ingestion. Query `filelog_events`, the destination table, to inspect the events.

## Write and score events

1. Append six synthetic events:

   ```bash
   python examples/write_filelog_events.py \
     .clickhouse/servers/demo/data/user_files/incident-filelog/app.log
   ```

   Run the command again to append six more events with new IDs. It does not truncate the file.

2. Check that the events reached the destination table:

   ```bash
   clickhousectl local client demo --query 'SELECT count() FROM filelog_events'
   ```

   The first run should produce `6`. Ingestion runs in the background; if you see `0`, wait a few seconds and run the query again.

3. Score the events:

   ```bash
   clickhousectl local client demo --queries-file examples/score-filelog-events.sql
   ```

   The query returns each event's features and a `risk` score. For example, a `checkout` event with code `500`, response time `1600`, and `2` retries produced `0.1491715293479955` with the sample model. Scores depend on the trained model.

## Rotation and recovery

In ClickHouse 26.10, FileLog can continue reading a tracked file after it is renamed during rotation. The `*.log` glob selects matching names when discovering files; a tracked file can still be read after its name changes. See the [ClickHouse 26.10 release notes](https://presentations.clickhouse.com/2026-release-26.10/).

FileLog is not a durable queue. A failure can cause missed events; [ClickHouse issue #111722](https://github.com/ClickHouse/ClickHouse/issues/111722) describes a possible loss after a crash. Retain source files and verify the destination before removing them. Replaying a file can insert duplicate events: the UUID in this example helps identify them but does not deduplicate the MergeTree table. `SYSTEM RESET FILELOG` changes the read position and requires a separate privilege; use it only when you have a recovery and deduplication plan.

To stop the server after the tutorial, follow [Stop or restart the server](local-demo.md#stop-or-restart-the-server).
