# CatBoost ClickHouse UDF SDK

Package a CatBoost model as an executable ClickHouse user-defined function (UDF). The worker loads the model once, accepts blocks of features over standard input, and returns one score per row.

This project is a prototype. The demo uses synthetic data and is not an incident detection system for production use.

The SDK supports binary classification and scalar regression models, numeric and categorical features, and the `TabSeparated` protocol with chunk headers. The bundle targets the ClickHouse Cloud Python 3.11 runtime. You can also run the example against a local ClickHouse server.

## Get started

- [Run the local demo](docs/local-demo.md). Train a model, load synthetic logs, and call the UDF in SQL.
- [Run the synthetic incident scenario](docs/synthetic-scenario.md). Compare scores across separate simulated time periods.
- [Package your model](docs/package-model.md). Validate a model and create a ZIP for ClickHouse Cloud.
- [Manifest and worker reference](docs/reference.md). Look up the feature contract and protocol.

The local demo was tested with Python 3.11, CatBoost 1.2.10, clickhousectl 0.6.0, and ClickHouse 26.10.6.18 on macOS ARM64. The Cloud upload has not been tested for this bundle. The demo labels are synthetic, so its scores do not establish performance on real incidents.

## Run the tests

From the project directory, use Python 3.11:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest -q
```

The tests train small models and check the manifest, package, worker protocol, and predictions. The local demo adds an integration check against ClickHouse.

## License

This project is available under the [MIT License](LICENSE).
