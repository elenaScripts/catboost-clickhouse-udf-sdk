import io
import json
import math
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from catboost import CatBoostClassifier, CatBoostRanker, CatBoostRegressor, Pool

from chcatboost.bundle import build_bundle
from chcatboost.manifest import ModelManifest, load_and_validate_model
from chcatboost.worker import _decode_tsv_row, _read_chunk


@pytest.fixture(scope="module")
def model_files(tmp_path_factory):
    root = tmp_path_factory.mktemp("models")
    x = [["a", 1.0], ["b", 2.0], ["a", 3.0], ["b", 4.0]] * 8
    pool = Pool(x, label=[0, 1, 0, 1] * 8, cat_features=[0], feature_names=["kind", "value"])
    classifier = CatBoostClassifier(iterations=12, verbose=False, allow_writing_files=False)
    classifier.fit(pool)
    model = root / "model.cbm"
    classifier.save_model(str(model))
    manifest = {"model_name": "risk", "version": "1", "task": "binary_classification", "positive_class": 1,
                "features": [{"name": "kind", "type": "categorical"}, {"name": "value", "type": "numeric"}]}
    path = root / "manifest.json"
    path.write_text(json.dumps(manifest))
    return root, classifier, model, path, manifest


def test_manifest_rejects_invalid_values(model_files, tmp_path):
    _, _, _, _, valid = model_files
    for changes in ({"model_name": "bad name"}, {"version": None}, {"task": []},
                    {"positive_class": None}, {"features": [{"name": 12, "type": "numeric"}]},
                    {"features": [{"name": "x", "type": []}]},
                    {"features": [{"name": "x", "type": "numeric"}, {"name": "x", "type": "numeric"}]}):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(valid | changes))
        with pytest.raises(ValueError):
            ModelManifest.from_file(path)


def test_model_contract_rejects_wrong_order_and_class(model_files, tmp_path):
    _, _, model, _, valid = model_files
    for changes in ({"features": list(reversed(valid["features"]))}, {"positive_class": 4}):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(valid | changes))
        with pytest.raises(ValueError):
            load_and_validate_model(model, ModelManifest.from_file(path))
    path.write_text(json.dumps({k: v for k, v in (valid | {"task": "regression"}).items() if k != "positive_class"}))
    with pytest.raises(ValueError, match="classifier"):
        load_and_validate_model(model, ModelManifest.from_file(path))


def test_bundle_and_worker_predictions(model_files, tmp_path):
    _, classifier, model, manifest, _ = model_files
    archive = build_bundle(model, manifest, tmp_path / "bundle.zip")
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist()) == {"main.py", "model.cbm", "manifest.json", "requirements.txt"}
        bundle.extractall(tmp_path / "worker")
    result = subprocess.run([sys.executable, str(tmp_path / "worker" / "main.py")],
                            input=b"2\na\t1\nb\t2\n1\na\t3\n", capture_output=True, check=True)
    actual = list(map(float, result.stdout.splitlines()))
    expected = classifier.predict_proba(Pool([["a", 1.0], ["b", 2.0], ["a", 3.0]],
                                            cat_features=[0], feature_names=["kind", "value"]))[:, 1]
    assert actual == pytest.approx(expected, abs=1e-14)
    bad = subprocess.run([sys.executable, str(tmp_path / "worker" / "main.py")],
                         input=b"1\n\\N\t1\n", capture_output=True)
    assert bad.returncode != 0
    assert b"Categorical feature" in bad.stderr


def test_bundle_does_not_overwrite_inputs(model_files):
    _, _, model, manifest, _ = model_files
    original = model.read_bytes()
    with pytest.raises(ValueError, match="Output path"):
        build_bundle(model, manifest, model)
    assert model.read_bytes() == original


def test_tsv_escaping_and_incomplete_chunks():
    assert _decode_tsv_row(r"hello\tworld" + "\t" + r"\N" + "\t" + r"\\N" + "\n") == ["hello\tworld", None, r"\N"]
    assert _read_chunk(io.BytesIO(b"0\n")) == []
    with pytest.raises(EOFError):
        _read_chunk(io.BytesIO(b"2\na\n"))
    with pytest.raises(ValueError):
        _read_chunk(io.BytesIO(b"-1\n"))


def test_regression_model(tmp_path):
    x = [[1.0], [2.0], [3.0], [4.0]]
    model = CatBoostRegressor(iterations=5, verbose=False, allow_writing_files=False)
    model.fit(Pool(x, label=[2.0, 4.0, 6.0, 8.0], feature_names=["value"]))
    model_path = tmp_path / "regression.cbm"
    model.save_model(str(model_path))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"model_name": "regression", "version": "1", "task": "regression",
                                         "features": [{"name": "value", "type": "numeric"}]}))
    archive = build_bundle(model_path, manifest_path, tmp_path / "regression.zip")
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(tmp_path / "worker")
    result = subprocess.run([sys.executable, str(tmp_path / "worker" / "main.py")],
                            input=b"2\n1\n3\n", capture_output=True, check=True)
    assert list(map(float, result.stdout.splitlines())) == pytest.approx(model.predict([[1.0], [3.0]]))


def test_rejects_ranking_and_multi_output_models(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"model_name": "score", "version": "1", "task": "regression",
                                         "features": [{"name": "value", "type": "numeric"}]}))
    manifest = ModelManifest.from_file(manifest_path)
    models = [
        (CatBoostRanker(iterations=3, loss_function="YetiRank", verbose=False, allow_writing_files=False),
         Pool([[1.0], [2.0], [3.0], [4.0]], label=[1, 0, 0, 1], group_id=[1, 1, 2, 2], feature_names=["value"])),
        (CatBoostRegressor(iterations=3, loss_function="MultiRMSE", verbose=False, allow_writing_files=False),
         Pool([[1.0], [2.0], [3.0], [4.0]], label=[[1, 2], [2, 3], [3, 4], [4, 5]], feature_names=["value"])),
    ]
    for index, (model, pool) in enumerate(models):
        model.fit(pool)
        model_path = tmp_path / f"unsupported-{index}.cbm"
        model.save_model(str(model_path))
        with pytest.raises(ValueError, match="Unsupported regression objective"):
            load_and_validate_model(model_path, manifest)
