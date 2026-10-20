"""Run the actual release builder against controlled repositories."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release.py"


def fixture(tmp_path):
    source = tmp_path / "repo" / "custom_components" / "wifimodule"
    (source / "frontend").mkdir(parents=True)
    (source / "__pycache__").mkdir()
    (source / "manifest.json").write_text(json.dumps({"version": "0.6.0"}))
    (source / "const.py").write_text('VERSION = "0.6.0"\n')
    (source / "__init__.py").write_text('"""Demo."""\n')
    (source / "frontend" / "panel.js").write_text('export const title = "Demo";\n')
    (source / "__pycache__" / "cached.pyc").write_bytes(b"exclude")
    (source / ".DS_Store").write_bytes(b"exclude")
    return source.parents[1]


def build(root, tag, output):
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(root),
            "--tag",
            tag,
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_release_packages_the_validated_version_and_checksum(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path / "dist"
    result = build(root, "0.6.0", output)
    assert result.returncode == 0, result.stderr
    archive = output / "jeremias-wifimodule-0.6.0-install.zip"
    with ZipFile(archive) as package:
        assert set(package.namelist()) == {
            "wifimodule/manifest.json",
            "wifimodule/const.py",
            "wifimodule/__init__.py",
            "wifimodule/frontend/panel.js",
        }
        assert (
            json.loads(package.read("wifimodule/manifest.json"))["version"] == "0.6.0"
        )
    assert archive.with_suffix(".zip.sha256").read_text() == (
        hashlib.sha256(archive.read_bytes()).hexdigest() + "  " + archive.name + "\n"
    )


def test_release_rejects_mismatched_or_prerelease_tags_without_artifacts(tmp_path):
    root = fixture(tmp_path)
    output = tmp_path / "dist"
    for tag in ("0.5.0", "0.6.0b1", "v0.6.0", "0.6.0-rc.1", "../0.6.0"):
        result = build(root, tag, output)
        assert result.returncode != 0
        assert "release" in result.stderr.lower(), result.stderr
        assert not output.exists()
    (root / "custom_components/wifimodule/const.py").write_text('VERSION = "0.5.0"\n')
    assert build(root, "0.6.0", output).returncode != 0
    assert not output.exists()
