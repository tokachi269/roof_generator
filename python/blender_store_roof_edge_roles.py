from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path


def _configure_script_path() -> None:
    candidates = []

    file_path = Path(__file__)
    candidates.append(file_path.parent)
    try:
        candidates.append(file_path.resolve().parent)
    except OSError:
        pass

    try:
        import bpy  # type: ignore

        current_name = file_path.name
        for text in bpy.data.texts:
            text_path = getattr(text, "filepath", "")
            if not text_path:
                continue
            path = Path(text_path)
            if path.name == current_name or current_name == "":
                candidates.append(path.parent)
    except Exception:
        pass

    for candidate in candidates:
        if not candidate:
            continue
        candidate_str = str(candidate)
        if (candidate / "blender_generate_roof_from_mesh.py").is_file() and candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)
            return


_configure_script_path()


def _reload_local_modules(*module_names: str) -> None:
    for module_name in module_names:
        module = importlib.import_module(module_name)
        importlib.reload(module)


_reload_local_modules(
    "blender_generate_roof_from_mesh",
    "blender_roof_role_props",
)

from blender_generate_roof_from_mesh import resolve_source_object
from blender_roof_role_props import clear_roof_edge_roles
from blender_roof_role_props import normalize_roof_role_code
from blender_roof_role_props import ROLE_NAME_TO_CODE
from blender_roof_role_props import set_selected_roof_edge_role
from blender_roof_role_props import store_roof_edge_roles
from blender_roof_role_props import summarize_roof_edge_roles


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Store roof_role_i on Blender mesh edges.")
    parser.add_argument("--object-name", default=None, help="Source Blender mesh object name. Defaults to the active object.")
    parser.add_argument("--role", default=None, help="Role name or code: none, eave, gable_end, shed_low, shed_high, parapet")
    parser.add_argument("--edge-indices-json", default=None, help="Optional JSON array of edge indices to assign")
    parser.add_argument("--selected-only", action="store_true", help="Assign the role to currently selected edges")
    parser.add_argument("--clear", action="store_true", help="Clear all nonzero roof_role_i values")
    parser.add_argument("--clear-existing", action="store_true", help="Clear existing roof_role_i values before writing new ones")
    return parser


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    args = build_argument_parser().parse_args(argv)

    import bpy

    source_object = resolve_source_object(bpy, args.object_name)
    mesh = source_object.data

    if args.clear:
        cleared_count = clear_roof_edge_roles(mesh)
        print(f"cleared_roles={cleared_count}, object={source_object.name}, summary={summarize_roof_edge_roles(mesh)}")
        return 0

    if args.role is None:
        available = ", ".join(sorted(ROLE_NAME_TO_CODE))
        raise ValueError(f"--role is required unless --clear is used; available roles: {available}")

    if args.edge_indices_json is not None:
        edge_indices = json.loads(args.edge_indices_json)
        if not isinstance(edge_indices, list):
            raise ValueError("edge_indices_json must decode to a JSON array")
        role_code = normalize_roof_role_code(args.role)
        stored = store_roof_edge_roles(
            mesh,
            {int(edge_index): role_code for edge_index in edge_indices},
            clear_existing=args.clear_existing,
        )
    elif args.selected_only:
        role_code, stored = set_selected_roof_edge_role(mesh, args.role, clear_existing=args.clear_existing)
    else:
        raise ValueError("choose either --edge-indices-json or --selected-only")

    print(
        f"stored_role={role_code}, stored_edges={len(stored)}, object={source_object.name}, summary={summarize_roof_edge_roles(mesh)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())