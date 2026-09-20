"""Verify wheel/sdist contents and installed Python/console entrypoints.

Run with the interpreter in a fresh environment containing the wheel and its
declared dependencies. This script never adds the source package to sys.path.
"""
import argparse
import base64
from email.parser import BytesParser
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = [path.name for path in (ROOT / "py").iterdir() if (path / "__init__.py").is_file()]
if len(PACKAGES) != 1:
    raise RuntimeError("Expected exactly one source package")
NAME = PACKAGES[0]
CASES = {
    "cletter": ("salutation", ["DE-LI", "Frau Dr. Müller"],
                {"locale": "DE-LI", "name": "Frau Dr. Müller"}, "Sehr geehrte Frau Dr. Müller"),
}


def check(condition, message):
    if not condition:
        raise AssertionError(message)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--wheel", type=Path, required=True)
parser.add_argument("--sdist", type=Path, required=True)
args = parser.parse_args()
licenses = {path.name: path.read_bytes() for path in (ROOT / "LICENSES").iterdir() if path.is_file()}
check(bool(licenses), "Source licenses are missing")
with zipfile.ZipFile(args.wheel) as wheel:
    files = wheel.namelist()
    check(f"{NAME}/py.typed" in files, "Wheel is missing py.typed")
    metadata_paths = [path for path in files if path.endswith(".dist-info/METADATA")]
    check(len(metadata_paths) == 1, "Expected one wheel distribution")
    metadata = BytesParser().parsebytes(wheel.read(metadata_paths[0]))
    check(metadata["Name"] == NAME, "Wheel package name differs from repository")
    check(metadata["License-Expression"] == "LGPL-3.0-only WITH LGPL-3.0-linking-exception", "Wheel must declare LGPL-3.0-only WITH LGPL-3.0-linking-exception")
    wheel_notices = {path.rsplit("/LICENSES/", 1)[1] for path in files if "/LICENSES/" in path}
    check(wheel_notices == set(licenses), "Wheel license inventory differs from the source notices")
    for name, expected in licenses.items():
        check(any(path.endswith("/LICENSES/" + name) and wheel.read(path) == expected for path in files),
              f"Wheel is missing the original {name}")
with tarfile.open(args.sdist, "r:gz") as sdist:
    files = {member.name: member for member in sdist.getmembers() if member.isfile()}
    for name, expected in licenses.items():
        check(any(path.endswith("/LICENSES/" + name) and sdist.extractfile(member).read() == expected
                  for path, member in files.items()), f"Source distribution is missing {name}")

distribution = importlib.metadata.distribution(NAME)
check(distribution.version == metadata["Version"], "Installed version differs from wheel")
check(any(entry.group == "console_scripts" and entry.name == NAME and entry.value == f"{NAME}.__main__:main"
          for entry in distribution.entry_points), "Missing console entrypoint metadata")
api = importlib.import_module(NAME)
check(not Path(api.__file__).resolve().is_relative_to(ROOT / "py"), "Imported source tree instead of installed wheel")
entrypoint = Path(sys.executable).parent / (NAME + (".exe" if os.name == "nt" else ""))
check(entrypoint.is_file(), "Installer did not create the console entrypoint")
function, positional, keywords, expected = CASES[NAME]

with tempfile.TemporaryDirectory(prefix=f"{NAME}-python-consumer-") as cwd:
    def call(command, function, values, *, stdin=False, valid=True):
        payload = values if isinstance(values, str) else json.dumps(values, ensure_ascii=False)
        result = subprocess.run(command + [function, "-" if stdin else payload],
                                input=payload if stdin else None, cwd=cwd, text=True,
                                encoding="utf-8", capture_output=True, timeout=30)
        if valid:
            check(result.returncode == 0, result.stderr)
            return json.loads(result.stdout)
        check(result.returncode == 2 and not result.stdout and "Traceback" not in result.stderr,
              f"Invalid arguments did not produce a clean CLI error: {result}")

    for command in ([sys.executable, "-m", NAME], [str(entrypoint)]):
        check(call(command, function, positional) == expected, "Positional JSON invocation failed")
        check(call(command, function, keywords, stdin=True) == expected, "Keyword/stdin invocation failed")
        call(command, function, "null", valid=False)
        call(command, function, "[NaN]", valid=False)
        call(command, function, [], valid=False)
        if NAME == "cletter":
            check(call(command, "normalize_locale_id", [" EN_CH "]) == "en-ch",
                  "Explicit locale-ID normalization is missing from the installed CLI")
    if NAME in ("cink", "cletter"):
        encoded = base64.b64encode(b'<svg xmlns="http://www.w3.org/2000/svg"/>').decode("ascii")
        decoded = call([str(entrypoint)], "normalize", [encoded])
        check(decoded["bytes"] == encoded and decoded["mime"] == "svg", "Image JSON output lost encoded bytes")
        check(call([str(entrypoint)], "signature_size", {"image": decoded, "height_pt": 20}) is None,
              "Image JSON output cannot be used as a subsequent input")
        raster = {"mime": "png", "width": 1, "height": 1, "bytes": ""}
        check(call([str(entrypoint)], "signature_size", {"image": raster, "height_pt": 10**400}) is None,
              "An unrepresentable height escaped the JSON bridge")
        check(call([str(entrypoint)], "signature_size", {"image": raster, "height_pt": 20, "max_width_pt": 10**400}) is None,
              "An unrepresentable maximum width escaped the JSON bridge")
print(f"Python {NAME}: installed module, console JSON calls, wheel/sdist licenses and metadata passed")
