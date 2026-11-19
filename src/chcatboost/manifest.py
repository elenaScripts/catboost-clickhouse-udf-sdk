"""Manifest loading and model compatibility checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from catboost import CatBoostClassifier, CatBoostRegressor


SUPPORTED_TASKS = {"binary_classification", "regression"}
SUPPORTED_FEATURE_TYPES = {"numeric", "categorical"}
# Other CatBoost objectives can represent rankings, vectors, or survival models.
# Accept only objectives with a single regression output.
SUPPORTED_REGRESSION_OBJECTIVES = {
    "RMSE", "MAE", "Quantile", "LogLinQuantile", "Poisson", "MAPE", "Lq",
    "Huber", "Tweedie", "LogCosh", "Expectile",
}


@dataclass(frozen=True)
class Feature:
    name: str
    type: str


@dataclass(frozen=True)
class ModelManifest:
    model_name: str
    version: str
    task: str
    features: tuple[Feature, ...]
    positive_class: Any = None

    @property
    def categorical_indices(self) -> list[int]:
        return [i for i, feature in enumerate(self.features) if feature.type == "categorical"]

    @classmethod
    def from_file(cls, path: str | Path) -> "ModelManifest":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Manifest root must be a JSON object")

        required = {"model_name", "version", "task", "features"}
        missing = sorted(required - raw.keys())
        if missing:
            raise ValueError(f"Manifest is missing required fields: {', '.join(missing)}")

        if not isinstance(raw["model_name"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", raw["model_name"]):
            raise ValueError("model_name must start with a letter and contain only letters, digits, and underscores")
        if not isinstance(raw["version"], str) or not raw["version"].strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(raw["task"], str) or raw["task"] not in SUPPORTED_TASKS:
            raise ValueError(f"task must be one of: {', '.join(sorted(SUPPORTED_TASKS))}")
        if not isinstance(raw["features"], list) or not raw["features"]:
            raise ValueError("features must be a non-empty list")

        features: list[Feature] = []
        for index, item in enumerate(raw["features"]):
            if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
                raise ValueError(f"features[{index}] must contain a non-empty string name")
            feature_type = item.get("type")
            if not isinstance(feature_type, str) or feature_type not in SUPPORTED_FEATURE_TYPES:
                raise ValueError(
                    f"features[{index}].type must be one of: "
                    f"{', '.join(sorted(SUPPORTED_FEATURE_TYPES))}"
                )
            features.append(Feature(name=item["name"], type=feature_type))

        names = [feature.name for feature in features]
        if len(names) != len(set(names)):
            raise ValueError("Feature names must be unique")

        positive_class = raw.get("positive_class")
        if raw["task"] == "binary_classification" and "positive_class" not in raw:
            raise ValueError("binary_classification requires positive_class in the manifest")
        if raw["task"] == "binary_classification" and (positive_class is None or not isinstance(positive_class, (str, int, float, bool))):
            raise ValueError("positive_class must be a string, number, or boolean")
        if raw["task"] == "regression" and positive_class is not None:
            raise ValueError("positive_class is only valid for binary_classification")

        return cls(
            model_name=raw["model_name"],
            version=raw["version"],
            task=raw["task"],
            features=tuple(features),
            positive_class=positive_class,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "model_name": self.model_name,
            "version": self.version,
            "task": self.task,
            "features": [{"name": f.name, "type": f.type} for f in self.features],
        }
        if self.task == "binary_classification":
            result["positive_class"] = self.positive_class
        return result


def load_and_validate_model(model_path: str | Path, manifest: ModelManifest):
    """Load a CatBoost model and check that its feature contract matches the manifest."""
    model_class = CatBoostClassifier if manifest.task == "binary_classification" else CatBoostRegressor
    model = model_class()
    model.load_model(str(model_path), format="cbm")

    if model.get_text_feature_indices() or model.get_embedding_feature_indices():
        raise ValueError("Text and embedding features are not supported")

    expected_names = [feature.name for feature in manifest.features]
    model_names = list(getattr(model, "feature_names_", []) or [])
    if len(model_names) != len(expected_names):
        raise ValueError(
            f"Model has {len(model_names)} features, manifest has {len(expected_names)}"
        )
    if model_names and model_names != expected_names:
        raise ValueError(
            "Feature order or names differ. "
            f"Model: {model_names}; manifest: {expected_names}"
        )

    model_cat_indices = sorted(model.get_cat_feature_indices())
    manifest_cat_indices = manifest.categorical_indices
    if model_cat_indices != manifest_cat_indices:
        raise ValueError(
            "Categorical feature positions differ. "
            f"Model: {model_cat_indices}; manifest: {manifest_cat_indices}"
        )

    if manifest.task == "binary_classification":
        classes = list(model.classes_)
        if len(classes) != 2:
            raise ValueError(f"Expected a binary model with 2 classes; found {len(classes)}")
        if manifest.positive_class not in classes:
            raise ValueError(
                f"positive_class {manifest.positive_class!r} is not in model classes {classes!r}"
            )
    elif len(model.classes_):
        raise ValueError("Manifest declares regression, but the model is a classifier")
    else:
        objective = model.get_all_params().get("loss_function", "")
        objective_name = objective.split(":", 1)[0] if isinstance(objective, str) else ""
        if objective_name not in SUPPORTED_REGRESSION_OBJECTIVES:
            raise ValueError(
                f"Unsupported regression objective {objective!r}; expected a supported scalar regression objective"
            )

    return model
