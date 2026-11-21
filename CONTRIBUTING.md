# Contributing

## Run the tests

From the project root, create a Python 3.11 environment and install the test dependencies:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest -q
```

The tests train small models and check the manifest, ZIP archive, worker protocol, and predictions. To check the UDF against a local ClickHouse server, follow the [local demo](docs/local-demo.md).
