# Reference

## Package requirements

The SDK requires Python 3.10 or newer and CatBoost version 1.2 or newer, but below 2. The local demo pins CatBoost 1.2.10 and clickhousectl 0.6.0. The CLI pins the CatBoost version installed in the build environment in each bundle's `requirements.txt`.

## CLI

### `catboost-ch inspect`

```text
catboost-ch inspect --model MODEL --manifest MANIFEST
```

| Option | Description |
| --- | --- |
| `--model` | Path to a CatBoost binary model. |
| `--manifest` | Path to the JSON feature manifest. |

Both options are required. On success, the command prints a JSON signature with the function name, argument names and types, return type, UDF settings, task, and model version. On validation or load failure, it prints an error to standard error and exits with code 2. Argument parsing errors also exit with code 2.

### `catboost-ch build`

```text
catboost-ch build --model MODEL --manifest MANIFEST --output ZIP
```

| Option | Description |
| --- | --- |
| `--model` | Path to a CatBoost `.cbm` model. |
| `--manifest` | Path to the JSON feature manifest. |
| `--output` | Destination for the ZIP archive. |

All options are required. The command validates the model, creates parent directories if needed, and replaces an existing output file. It rejects an output path that resolves to the model or manifest. On success, it prints the output path. On failure, it prints an error to standard error and exits with code 2.

## Python API

`chcatboost.bundle.build_bundle(model_path, manifest_path, output_path)` validates the model and writes the same ZIP as the CLI. It accepts strings or `pathlib.Path` objects and returns the resolved output path as a `Path`. It raises an exception if validation or file operations fail.

```python
from chcatboost.bundle import build_bundle

output = build_bundle(
    "dist/quickstart/incident-risk.cbm",
    "examples/incident-risk.manifest.json",
    "dist/quickstart/incident-risk-udf.zip",
)
print(output)
```

`chcatboost.manifest.ModelManifest.from_file(path)` reads and validates a manifest. `chcatboost.manifest.load_and_validate_model(model_path, manifest)` loads the model, checks its feature contract, and returns the CatBoost model. Validation errors raise `ValueError`; file and CatBoost errors may also propagate.

## Manifest

The manifest is a JSON object with these fields:

| Field | Type | Description |
| --- | --- | --- |
| `model_name` | string | Function name. It starts with an ASCII letter and contains ASCII letters, digits, or underscores. |
| `version` | string | Non-empty model version. |
| `task` | string | `binary_classification` or `regression`. |
| `positive_class` | string, number, or boolean | Required for binary classification. The value must occur in the model's classes. |
| `features` | array | Non-empty ordered list of features. |

Each feature has a unique non-empty string `name` and a `type` of `numeric` or `categorical`. The SDK checks feature names, order, count, and categorical positions against the model. For regression, `positive_class` must be absent or `null`. The model must carry the feature names used in the manifest. See the [example manifest](../examples/incident-risk.manifest.json).

The SDK rejects text and embedding features. For regression, supported objectives are `RMSE`, `MAE`, `Quantile`, `LogLinQuantile`, `Poisson`, `MAPE`, `Lq`, `Huber`, `Tweedie`, `LogCosh`, and `Expectile`. Ranking, multiclass classification, multi-output regression, arrays, text features, and embeddings are outside the supported contract.

## Function signature

`inspect` reports a `Nullable(String)` argument for each categorical feature and a `Nullable(Float64)` argument for each numeric feature. Arguments follow the manifest order. The return type is `Float64`. For a binary classifier, the result is the probability of `positive_class`. For a regressor, the result is the raw prediction.

## UDF configuration

The generated worker expects the following executable UDF settings:

| Setting | Value | Description |
| --- | --- | --- |
| `type` | `executable_pool` | Reuse a pool of worker processes across blocks. |
| `format` | `TabSeparated` | Serialize function arguments and results as tab-separated data. |
| `send_chunk_header` | `true` | Send the row count before each block. |
| `return_type` | `Float64` | Return one floating-point value per input row. |

The local demo uses the Python interpreter from its virtual environment. For ClickHouse Cloud, `inspect` reports the `python3.11` runtime. The SDK reports `deterministic: true` for a fixed model and input. See [User-defined functions in Cloud](https://clickhouse.com/docs/products/cloud/features/sql-console-features/user-defined-functions) for Cloud settings and [Executable user-defined functions](https://clickhouse.com/docs/reference/functions/regular-functions/udf) for self-managed configuration.

## Bundle

The ZIP contains the following files at its root:

| File | Contents |
| --- | --- |
| `main.py` | Executable worker code. |
| `manifest.json` | Validated manifest. |
| `model.cbm` | Model copied from the input path. |
| `requirements.txt` | The installed CatBoost version, pinned with `==`. |

The archive does not contain the CatBoost package itself. The target runtime must install the dependency. The generated bundle has not been tested in ClickHouse Cloud.

## Worker protocol

The worker uses `TabSeparated` input with a chunk header. It reads a decimal row count followed by that many rows. It writes one finite floating-point value per row and flushes after each block. The worker loads the model once at process start and handles multiple blocks until input ends.

The worker converts numeric `NULL` to NaN. The model must support missing numeric values. The worker rejects categorical `NULL`, malformed rows, incomplete blocks, and non-finite predictions. On an error, it writes a message to standard error and exits with code 1. The worker accepts an empty block and writes no result rows for it.
