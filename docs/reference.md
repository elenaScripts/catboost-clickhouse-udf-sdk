# Manifest and worker reference

## Manifest

The manifest is a JSON object with these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `model_name` | string | Function name. It starts with a letter and contains letters, digits, or underscores. |
| `version` | string | Non-empty model version. |
| `task` | string | `binary_classification` or `regression`. |
| `positive_class` | string, number, or boolean | Required for binary classification. The value must occur in the model's classes. |
| `features` | array | Non-empty ordered list of features. |

Each feature has a unique non-empty string `name` and a `type` of `numeric` or `categorical`. The SDK checks the number, names, order, and categorical positions against the model. The model must carry the feature names used in the manifest.

## Function signature

`inspect` reports a `Nullable(String)` argument for each categorical feature and a `Nullable(Float64)` argument for each numeric feature. The return type is `Float64`. For a binary classifier, the score is the probability of `positive_class`. For a regressor, the score is the raw prediction.

Supported regression objectives are `RMSE`, `MAE`, `Quantile`, `LogLinQuantile`, `Poisson`, `MAPE`, `Lq`, `Huber`, `Tweedie`, `LogCosh`, and `Expectile`. The SDK rejects other regression objectives, including ranking and multi-output objectives.

## Worker protocol

The worker reads a decimal row count followed by that many `TabSeparated` rows. It writes one finite floating-point value per input row and flushes after each block. Numeric `NULL` becomes NaN. The worker rejects categorical `NULL`, malformed rows, and non-finite predictions. Normalize missing categories before calling the function. The worker exits with an error if it cannot score a block.

## Bundle

The ZIP contains `main.py`, `manifest.json`, `model.cbm`, and `requirements.txt` at its root. The requirements file pins the CatBoost version installed in the packaging environment. `build` replaces an existing output ZIP but rejects an output path that matches the model or manifest.

The SDK does not support text features, embeddings, arrays, multiclass output, ranking, or multi-output regression. It does not provide a model registry, Cloud deployment, automatic rollback, or a throughput guarantee.
