from __future__ import annotations

import json
from typing import Any


DEFAULT_SOLVER_CONFIG = {
    "mesh_name": "roof",
    "roof_height": 50.0,
    "lambda_weight": 0.0,
    "fixed_roof_vertex_id": None,
    "separation_factor": 1.25,
}


def normalize_solver_config(raw_config: dict[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if "mesh_name" in raw_config and raw_config["mesh_name"] is not None:
        config["mesh_name"] = str(raw_config["mesh_name"])
    if "roof_height" in raw_config and raw_config["roof_height"] is not None:
        config["roof_height"] = float(raw_config["roof_height"])
    if "lambda_weight" in raw_config and raw_config["lambda_weight"] is not None:
        config["lambda_weight"] = float(raw_config["lambda_weight"])
    if "fixed_roof_vertex_id" in raw_config:
        value = raw_config["fixed_roof_vertex_id"]
        config["fixed_roof_vertex_id"] = None if value is None else int(value)
    if "separation_factor" in raw_config and raw_config["separation_factor"] is not None:
        config["separation_factor"] = float(raw_config["separation_factor"])
    return config


def decode_solver_config(raw_config) -> dict[str, Any] | None:
    if raw_config is None:
        return None
    if isinstance(raw_config, str):
        return normalize_solver_config(json.loads(raw_config))
    return normalize_solver_config(dict(raw_config))


def encode_solver_config(config: dict[str, Any]) -> str:
    normalized = normalize_solver_config(config)
    return json.dumps(normalized)


def store_solver_config(target, config: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_solver_config(config)
    target["roof_solver_config"] = encode_solver_config(normalized)
    return normalized


def clear_solver_config(target) -> bool:
    if "roof_solver_config" in target:
        del target["roof_solver_config"]
        return True
    return False


def read_solver_config(source_object) -> dict[str, Any] | None:
    raw_config = source_object.get("roof_solver_config")
    if raw_config is None:
        raw_config = source_object.data.get("roof_solver_config")
    return decode_solver_config(raw_config)


def resolve_solver_config(
    overrides: dict[str, Any] | None = None,
    stored_config: dict[str, Any] | None = None,
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = dict(DEFAULT_SOLVER_CONFIG if defaults is None else defaults)
    if stored_config:
        resolved.update(normalize_solver_config(stored_config))
    if overrides:
        resolved.update({key: value for key, value in normalize_solver_config(overrides).items() if value is not None or key == "fixed_roof_vertex_id"})
        if "fixed_roof_vertex_id" in overrides and overrides["fixed_roof_vertex_id"] is None:
            resolved["fixed_roof_vertex_id"] = None
    return resolved
