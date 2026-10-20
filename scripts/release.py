"""Build an installable archive only when a canonical release tag matches the code."""

import argparse
import ast
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def build_release(root: Path, tag: str, output: Path) -> Path:
    if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", tag):
        raise ValueError(
            "Release tag must be a plain X.Y.Z version, without v or prerelease suffix"
        )
    source = root / "custom_components" / "wifimodule"
    manifest = json.loads((source / "manifest.json").read_text())
    tree = ast.parse((source / "const.py").read_text())
    versions = [
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "VERSION"
            for target in node.targets
        )
    ]
    if manifest.get("version") != tag or versions != [tag]:
        raise ValueError("Release tag, manifest version and VERSION must match exactly")
    files = sorted(
        path
        for path in source.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and not any(
            part.startswith(".") or part == "__pycache__"
            for part in path.relative_to(source).parts
        )
        and path.suffix not in (".pyc", ".pyo")
    )
    license_text = (root / "LICENSE").read_text()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"jeremias-wifimodule-{tag}-install.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as package:
        package.writestr("LICENSE", license_text)
        for path in files:
            package.write(
                path, Path("custom_components/wifimodule") / path.relative_to(source)
            )
    archive.with_suffix(".zip.sha256").write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n"
    )
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(build_release(args.root, args.tag, args.output))
    except (ValueError, OSError, SyntaxError) as err:
        parser.exit(1, f"Release rejected: {err}\n")


if __name__ == "__main__":
    main()
