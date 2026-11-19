# Package a model for ClickHouse Cloud

Use this guide when you have a trained CatBoost `.cbm` file and a feature manifest. Install the SDK in a Python environment that has the CatBoost version you want in the UDF runtime. The generated ZIP pins that version.

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

4. In ClickHouse Cloud, create a Python executable UDF using the ZIP. Use the signature from `inspect`, `executable_pool`, `python3.11`, `TabSeparated`, and a chunk header. Choose a pool size that fits your memory budget. Each worker loads its own model copy.

5. Compare SQL scores with direct CatBoost predictions on representative data. Measure throughput and latency before using the function on a large table.

The bundle in this repository has not been tested in ClickHouse Cloud. The SDK does not deploy it or manage model versions. For current Cloud settings, see [ClickHouse executable UDF documentation](https://clickhouse.com/docs/products/cloud/features/sql-console-features/user-defined-functions).
