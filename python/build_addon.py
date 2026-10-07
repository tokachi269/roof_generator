"""Build a reproducible Blender addon ZIP, excluding optimizer/reference assets."""

import argparse
import io
from pathlib import Path
import zipfile


def build(output, check=False):
    source = Path(__file__).resolve().parent.parent / "addon" / "roof_generator"
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        p
        for p in source.rglob("*")
        if p.is_file()
        and not any(
            x == "__pycache__" or x.startswith(".") for x in p.relative_to(source).parts
        )
        and (p.suffix in (".py", ".md") or p.name == "LICENSE")
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            item = zipfile.ZipInfo(
                "roof_generator/" + file.relative_to(source).as_posix(),
                date_time=(2020, 1, 1, 0, 0, 0),
            )
            item.compress_type = zipfile.ZIP_DEFLATED
            # ZipInfo otherwise records the host OS (0 on Windows, 3 on Unix).
            item.create_system = 3
            item.external_attr = 0o644 << 16
            archive.writestr(item, file.read_bytes())
    if check:
        if not output.is_file() or output.read_bytes() != buffer.getvalue():
            raise SystemExit(f"Addon ZIP is missing or out of date: {output}")
        print(f"Addon ZIP matches source: {output}")
    else:
        output.write_bytes(buffer.getvalue())
        print(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dist/roof_generator-1.0.0.zip")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check the existing ZIP against canonical source",
    )
    args = parser.parse_args()
    build(args.output, check=args.check)
