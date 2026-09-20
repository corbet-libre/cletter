#!/usr/bin/env python3
"""Validate the published Python release using its exact producing source."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import tomllib


ROOT = Path(__file__).resolve().parents[1]
RELEASE_COMMIT = "52e8c09794643f63f22972833b16ded7021eb574"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    require(os.environ.get("CI") == "crow"
            and os.environ.get("CI_REPO") == "corbet-foss/cletter"
            and os.environ.get("CI_PIPELINE_EVENT") == "manual",
            "Historical Python validation requires the manual cletter Crow route")
    driver_commit = os.environ.get("CI_COMMIT_SHA", "")
    require(re.fullmatch(r"[0-9a-f]{40}", driver_commit), "Missing driver commit")
    pinned = tomllib.loads((ROOT / ".ci/archives.toml").read_text())["archives"]["pypi-release"]
    require(pinned == {
        "revision": RELEASE_COMMIT, "archive_variable": "PYPI_SOURCE_ARCHIVE",
        "digest_variable": "PYPI_SOURCE_SHA256", "workflows": ["published-python-release"],
    }, "Historical release archive declaration changed")
    source_sha256 = os.environ.get("PYPI_SOURCE_SHA256", "")
    require(re.fullmatch(r"[0-9a-f]{64}", source_sha256), "Missing release source digest")
    artifact_root = os.environ.get("ARTIFACT_ROOT", "")
    require(artifact_root and Path(artifact_root).is_absolute(), "ARTIFACT_ROOT must be absolute")
    parent = Path(artifact_root) / "cletter" / RELEASE_COMMIT / "published-python"
    parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=parent))
    receipt = {
        "schema": 1, "provider": "crow", "repository": "corbet-foss/cletter",
        "check": "published-python", "version": "0.2.1",
        "driver_commit": driver_commit, "driver_source_sha256": os.environ.get("SOURCE_SHA256"),
        "source_commit": RELEASE_COMMIT, "source_sha256": source_sha256,
        "tool_revision": os.environ.get("CCID_REVISION"),
        "tool_binary_sha256": os.environ.get("CI_TOOL_BINARY_SHA256"),
        "run": os.environ.get("CI_PIPELINE_NUMBER", os.environ.get("CI_BUILD_NUMBER")),
        "python": sys.version.split()[0],
        "uv": subprocess.check_output(["uv", "--version"], text=True).strip(),
        "started": int(time.time()), "status": "running",
        "scope": "PyPI cletter 0.2.1 installed vectors and module CLI; no package rebuild",
    }
    try:
        with tempfile.TemporaryDirectory(prefix="cletter-pypi-release-") as temporary:
            source = Path(temporary) / "source"
            subprocess.run([
                os.environ["CI_TOOL_BINARY"], "verify-source",
                "--archive", os.environ["PYPI_SOURCE_ARCHIVE"],
                "--sha256", source_sha256, "--commit", RELEASE_COMMIT,
                "--destination", str(source),
            ], check=True)
            package = tomllib.loads((source / "Cargo.toml").read_text())["package"]
            require(package["name"] == "cletter" and package["version"] == "0.2.1",
                    "Historical source does not describe cletter 0.2.1")
            receipt["check_script_sha256"] = digest(source / ".ci/check.py")
            receipt["conformance_script_sha256"] = digest(source / "py/scripts/conformance.py")
            subprocess.run([sys.executable, ".ci/check.py", "published-python"], cwd=source,
                           env={**os.environ, "CI_COMMIT_SHA": RELEASE_COMMIT,
                                "SOURCE_ARCHIVE": os.environ["PYPI_SOURCE_ARCHIVE"],
                                "SOURCE_SHA256": source_sha256,
                                "UV_PYTHON_DOWNLOADS": "never", "PYTHONDONTWRITEBYTECODE": "1"},
                           check=True)
        receipt["status"] = "success"
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        receipt["status"] = "failure"
        raise
    finally:
        receipt["finished"] = int(time.time())
        (output / "published-python.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"artifact_directory": str(output), "receipt": receipt}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
