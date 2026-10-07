from __future__ import annotations

from typing import Iterable


ROLE_NAME_TO_CODE = {
    "none": 0,
    "eave": 1,
    "gable_end": 2,
    "shed_low": 3,
    "shed_high": 4,
    "parapet": 5,
}

ROLE_CODE_TO_NAME = {value: key for key, value in ROLE_NAME_TO_CODE.items()}


def normalize_roof_role_code(role: int | str) -> int:
    if isinstance(role, str):
        normalized = role.strip().lower()
        if normalized not in ROLE_NAME_TO_CODE:
            raise ValueError(f"unsupported roof role '{role}'")
        return ROLE_NAME_TO_CODE[normalized]

    role_code = int(role)
    if role_code not in ROLE_CODE_TO_NAME:
        raise ValueError(f"unsupported roof role code {role_code}")
    return role_code


def ensure_roof_role_attribute(mesh):
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        raise ValueError("mesh does not support Blender attributes")

    attribute = attributes.get("roof_role_i")
    if attribute is None:
        attribute = attributes.new(name="roof_role_i", type="INT", domain="EDGE")
    return attribute


def clear_roof_edge_roles(mesh) -> int:
    attribute = _get_roof_role_attribute(mesh)
    if attribute is None:
        return 0

    cleared_count = 0
    for entry in attribute.data:
        if int(entry.value) != 0:
            entry.value = 0
            cleared_count += 1
    return cleared_count


def store_roof_edge_roles(mesh, edge_role_map: dict[int, int | str], clear_existing: bool = False) -> dict[int, int]:
    attribute = ensure_roof_role_attribute(mesh)
    if clear_existing:
        for entry in attribute.data:
            entry.value = 0

    normalized = {}
    edge_count = len(getattr(mesh, "edges", ()))
    for edge_index, raw_role in edge_role_map.items():
        edge_index = int(edge_index)
        if edge_index < 0 or edge_index >= edge_count:
            raise ValueError(f"edge index {edge_index} is out of range")
        role_code = normalize_roof_role_code(raw_role)
        attribute.data[edge_index].value = role_code
        normalized[edge_index] = role_code
    return normalized


def set_selected_roof_edge_role(mesh, role: int | str, clear_existing: bool = False) -> tuple[int, dict[int, int]]:
    role_code = normalize_roof_role_code(role)
    selected_edge_ids = tuple(_selected_edge_indices(mesh))
    if not selected_edge_ids:
        raise ValueError("no selected mesh edges found")

    stored = store_roof_edge_roles(
        mesh,
        {edge_index: role_code for edge_index in selected_edge_ids},
        clear_existing=clear_existing,
    )
    return role_code, stored


def read_roof_edge_roles(mesh) -> dict[int, int]:
    attribute = _get_roof_role_attribute(mesh)
    if attribute is None:
        return {}
    return {
        edge_index: int(attribute.data[edge_index].value)
        for edge_index in range(len(attribute.data))
        if int(attribute.data[edge_index].value) != 0
    }


def summarize_roof_edge_roles(mesh) -> str:
    role_values = read_roof_edge_roles(mesh)
    if not role_values:
        return "roof_role_i=missing_or_zero"

    counts = {}
    for role_code in role_values.values():
        counts[role_code] = counts.get(role_code, 0) + 1
    parts = [f"nonzero_edges={len(role_values)}"]
    for role_code in sorted(counts):
        parts.append(f"{ROLE_CODE_TO_NAME.get(role_code, str(role_code))}={counts[role_code]}")
    return ", ".join(parts)


def _get_roof_role_attribute(mesh):
    attributes = getattr(mesh, "attributes", None)
    if attributes is None:
        return None
    return attributes.get("roof_role_i")


def _selected_edge_indices(mesh) -> Iterable[int]:
    for edge in getattr(mesh, "edges", ()):
        if getattr(edge, "select", False):
            yield int(edge.index)