# Package a model for ClickHouse Cloud

Package a trained CatBoost `.cbm` model as an executable user-defined function (UDF) archive. The generated archive has not been tested in ClickHouse Cloud.

## Prerequisites

- A trained CatBoost model and a JSON feature manifest.
- The SDK installed in a Python environment with the CatBoost version you want in the UDF runtime. The archive pins that version in `requirements.txt`.

## Create the archive

1. Create a JSON manifest with the feature names, order, types, and task of the model. For a binary classifier, specify the positive class. See the [manifest reference](reference.md) and the [example manifest](../examples/incident-risk.manifest.json).

2. Check the model against the manifest.

   ```bash
   catboost-ch inspect --model path/to/model.cbm --manifest path/to/manifest.json
   ```

   The command prints the function signature as JSON. It exits with code 2 if validation fails.

3. Create the ZIP.

   ```bash
   catboost-ch build --model path/to/model.cbm --manifest path/to/manifest.json --output dist/model-udf.zip
   ```

4. In ClickHouse Cloud, create an executable UDF using the ZIP archive. Use the function name, arguments, and return type from the `inspect` response. Configure the following settings:

   | Setting | Value |
   | --- | --- |
   | Type | `executable_pool` |
   | Runtime type | `python3.11` |
   | Format | `TabSeparated` |
   | Send chunk header | Enabled |
   | Deterministic | Enabled |

   Choose a pool size that fits your memory budget. Each process loads its own model copy.

5. Compare SQL scores with direct CatBoost predictions on representative data. Measure throughput and latency before using the function on a large table.

The SDK does not deploy the archive or manage model versions. For the Cloud UDF workflow and configuration settings, see [User-defined functions in Cloud](https://clickhouse.com/docs/products/cloud/features/sql-console-features/user-defined-functions).
