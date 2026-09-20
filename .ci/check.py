#!/usr/bin/env python3
"""Focused package checks; CI providers supply scheduling and credentials."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]
NAME, VERSION = PACKAGE["name"], PACKAGE["version"]
JS = ROOT / "js" / "@corbet-foss" / NAME


def run(*args, cwd=None, env=None):
    print("+ " + " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=ROOT if cwd is None else cwd, env=env, check=True)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def artifact_directory():
    base, commit = os.environ.get("ARTIFACT_ROOT"), os.environ.get("CI_COMMIT_SHA", "")
    if not base or not Path(base).is_absolute() or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Package checks require an absolute ARTIFACT_ROOT and exact CI_COMMIT_SHA")
    directory = Path(base) / NAME / commit
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def preserve(path, data):
    """Install immutable evidence without replacing a different existing artifact."""
    try:
        with path.open("xb") as stream:
            stream.write(data)
    except FileExistsError:
        if path.read_bytes() != data:
            raise ValueError(f"Existing release artifact differs: {path.name}") from None


def export(check, paths):
    directory = artifact_directory()
    manifest = {}
    for source in paths:
        source = Path(source)
        preserve(directory / source.name, source.read_bytes())
        manifest[source.name] = digest(source)
    preserve(directory / "SOURCE_COMMIT", (os.environ["CI_COMMIT_SHA"] + "\n").encode())
    receipt = {
        "schema": 1, "package": NAME, "version": VERSION, "check": check,
        "commit": os.environ["CI_COMMIT_SHA"],
        "source_sha256": os.environ.get("SOURCE_SHA256"),
        "tool_revision": os.environ.get("CCID_REVISION"),
        "dependency_manifest_sha256": os.environ.get("DEPENDENCY_MANIFEST_SHA256"),
        "artifacts": manifest,
    }
    preserve(directory / f"{check}.json", (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    hashes = {path.name: digest(path) for path in directory.iterdir()
              if path.is_file() and path.suffix in {".crate", ".tgz", ".whl", ".gz", ".lock"}}
    # This aggregate index is derived; individual artifacts and receipts are immutable.
    index = directory / f".SHA256SUMS.{os.getpid()}"
    index.write_text("".join(f"{value}  {name}\n" for name, value in sorted(hashes.items())))
    index.replace(directory / "SHA256SUMS")
    print(json.dumps({"artifact_directory": str(directory), "receipt": receipt}, sort_keys=True))


def metadata():
    run("python3", "scripts/check-versions.py")
    generated = [JS / "src/generated", ROOT / "typst/generated", ROOT / "py" / NAME / "_tables.py"]
    paths = [p for entry in generated for p in (entry.rglob("*") if entry.is_dir() else [entry]) if p.is_file()]
    before = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    run("bash", JS / "scripts/sync-assets.sh")
    paths = [p for entry in generated for p in (entry.rglob("*") if entry.is_dir() else [entry]) if p.is_file()]
    after = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    if before != after:
        changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
        raise ValueError("Generated assets differ: " + ", ".join(changed))


def js_install():
    run("bun", "install", "--frozen-lockfile", cwd=JS)


def javascript():
    js_install()
    run("bun", "run", "typecheck", cwd=JS)
    run("bun", "run", "conformance", cwd=JS)


def npm_tarball():
    return JS / f"corbet-foss-{NAME}-{VERSION}.tgz"


def js_package():
    artifact_directory()
    js_install()
    run("npm", "pack", cwd=JS)
    tarball = npm_tarball()
    run("node", "scripts/pack-check.mjs", cwd=JS,
        env={**os.environ, "TEST_MANAGER": "npm", "TEST_TARBALL": str(tarball)})
    run("deno", "publish", "--dry-run", "--allow-dirty", cwd=JS)
    run("deno", "eval", "import {verify} from './scripts/verify-api.mjs'; import * as api from './dist/browser.js'; verify(api);", cwd=JS)
    export("js-package", [tarball])


def js_manager(manager):
    # Additional managers consume a previous verified tarball from this exact source.
    directory = artifact_directory()
    receipt = json.loads((directory / "js-package.json").read_text())
    tarball = directory / npm_tarball().name
    if receipt["commit"] != os.environ["CI_COMMIT_SHA"] or receipt["artifacts"].get(tarball.name) != digest(tarball):
        raise ValueError("JavaScript artifact identity differs from its receipt")
    js_install()
    run("node", "scripts/pack-check.mjs", cwd=JS,
        env={**os.environ, "TEST_MANAGER": manager, "TEST_TARBALL": str(tarball)})
    export(f"js-{manager}", [tarball])


def dependencies(directory, kind):
    source = os.environ.get("DEPENDENCY_MANIFEST")
    expected = os.environ.get("DEPENDENCY_MANIFEST_SHA256")
    if not source and not expected:
        return []
    if not source or not expected or digest(source) != expected:
        raise ValueError("Dependency manifest SHA-256 mismatch")
    manifest = json.loads(Path(source).read_text())
    if manifest.get("schema") != 1:
        raise ValueError("Dependency manifest requires schema 1")
    result = []
    for item in manifest["artifacts"]:
        if item["kind"] != kind:
            continue
        source = Path(item["path"])
        payload = source.read_bytes()
        if hashlib.sha256(payload).hexdigest() != item["sha256"]:
            raise ValueError("Dependency artifact SHA-256 mismatch")
        copied = directory / source.name
        preserve(copied, payload)
        result.append((item["name"], copied))
    return result


def python_package():
    artifact_directory()
    with tempfile.TemporaryDirectory(prefix=f"{NAME}-python-") as temporary:
        scratch = Path(temporary)
        output = scratch / "dist"
        run("uv", "build", "py", "--out-dir", output)
        wheels, sdists = list(output.glob("*.whl")), list(output.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise ValueError("Expected exactly one Python wheel and sdist")
        venv = scratch / "consumer"
        run("uv", "venv", venv)
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        wheels_to_install = [path for _, path in dependencies(scratch, "wheel")]
        run("uv", "pip", "install", "--python", python, *wheels_to_install, wheels[0])
        run(python, ROOT / "py/scripts/conformance.py", "--installed", cwd=scratch)
        run(python, ROOT / "py/scripts/consumer.py", "--wheel", wheels[0], "--sdist", sdists[0], cwd=scratch)
        export("python-package", [*wheels, *sdists])


def typst_package():
    artifact_directory()
    run("uv", "run", "--with", "typst==0.15.0", "python", "scripts/package-typst.py")
    export("typst-package", [ROOT / "dist" / f"{NAME}-{VERSION}-typst.tar.gz"])


def typst_conformance():
    artifact_directory()
    run("uv", "run", "--offline", "--no-python-downloads", "--with", "typst==0.15.0",
        "python", "scripts/typst-conformance.py", ROOT.parent, NAME)
    export("typst-conformance", [])


def typst_family_preview():
    artifact_directory()
    with tempfile.TemporaryDirectory(prefix="cletter-preview-input-") as temporary:
        candidates = dependencies(Path(temporary), "typst-preview")
        if {name for name, _ in candidates} != {"cdate", "cfarewell", "cink", "cletter"}:
            raise ValueError("Expected the four Apache family preview archives")
        paths = [path for _, path in candidates]
        run("uv", "run", "--with", "typst==0.15.0", "python", ".ci/typst-family-preview.py", *paths)
        export("typst-family-preview", paths)


def rust_package():
    artifact_directory()
    run("cargo", "package", "--locked")
    target = Path(os.environ.get("CARGO_TARGET_DIR", ROOT / "target"))
    export("rust-package", [target / "package" / f"{NAME}-{VERSION}.crate"])


def rust_dependencies():
    """Pre-publication integration only; registry packaging remains a separate check."""
    artifact_directory()
    with tempfile.TemporaryDirectory(prefix=f"{NAME}-rust-dependencies-") as temporary:
        scratch = Path(temporary)
        crates = dependencies(scratch, "crate")
        if not crates:
            raise ValueError("rust-dependencies requires exact verified sibling crate artifacts")
        source = scratch / "source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "target", "node_modules", "dist"))
        patches = ["[patch.crates-io]"]
        for name, crate in crates:
            destination = scratch / (name + "-dependency")
            destination.mkdir()
            with tarfile.open(crate, "r:gz") as archive:
                archive.extractall(destination, filter="data")
            roots = list(destination.iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise ValueError("Expected one crate package root")
            metadata = tomllib.loads((roots[0] / "Cargo.toml").read_text())["package"]
            if metadata["name"] != name:
                raise ValueError("Dependency crate name differs from the manifest")
            patches.append(f"{json.dumps(name)} = {{path = {json.dumps(str(roots[0]))}}}")
        config = scratch / "dependencies.toml"
        config.write_text("\n".join(patches) + "\n")
        # Only this private scratch lock is changed. Published source keeps registry resolution.
        run("cargo", "--config", config, "generate-lockfile", "--offline", cwd=source)
        run("cargo", "fmt", "--check", cwd=source)
        run("cargo", "--config", config, "clippy", "--locked", "--all-targets", "--", "-D", "warnings", cwd=source)
        run("cargo", "--config", config, "test", "--locked", cwd=source)
        export("rust-dependencies", [])


def resolve_dependencies():
    """Resolve published sibling versions in scratch; export locks for review."""
    artifact_directory()
    crate_manifest = tomllib.loads((ROOT / "Cargo.toml").read_text())
    if "patch" in crate_manifest or "replace" in crate_manifest:
        raise ValueError("Registry lock resolution must not use Cargo patches or replacements")
    siblings = ("cgreet", "cfarewell", "cdate", "cink")
    selected = []
    for name in siblings:
        dependency = crate_manifest["dependencies"][name]
        if not isinstance(dependency, str):
            raise ValueError("Sibling Cargo dependencies must declare registry versions directly")
        selected.extend(("-p", name))
    # Update only the four sibling dependency closures, preserving unrelated pins.
    run("cargo", "update", *selected)
    locked = tomllib.loads((ROOT / "Cargo.lock").read_text())["package"]
    for name in siblings:
        expected = crate_manifest["dependencies"][name]
        matches = [package for package in locked if package["name"] == name]
        if (len(matches) != 1 or matches[0]["version"] != expected
                or matches[0].get("source") != "registry+https://github.com/rust-lang/crates.io-index"
                or not re.fullmatch(r"[0-9a-f]{64}", matches[0].get("checksum", ""))):
            raise ValueError(f"Expected exactly the published crates.io version {name}@{expected}")
    run("bun", "install", "--lockfile-only", "--ignore-scripts", cwd=JS)
    export("resolve-dependencies", [ROOT / "Cargo.lock", JS / "bun.lock"])


def published(channel):
    with tempfile.TemporaryDirectory(prefix=f"{NAME}-{channel}-") as temporary:
        scratch = Path(temporary)
        if channel in {"npm", "jsr"}:
            for name in ["consumer.mjs", "verify-api.mjs"]:
                shutil.copyfile(JS / "scripts" / name, scratch / name)
            (scratch / "package.json").write_text('{"private":true,"type":"module"}\n')
        if channel == "npm":
            run("npm", "install", "--ignore-scripts", "--no-audit", "--no-fund", f"@corbet-foss/{NAME}@{VERSION}", cwd=scratch)
            run("node", "consumer.mjs", cwd=scratch)
            run("bun", "consumer.mjs", cwd=scratch)
        elif channel == "jsr":
            run("deno", "eval", "--node-modules-dir=auto", "--min-dep-age=0", f"import * as api from 'jsr:@corbet-foss/{NAME}@{VERSION}'; import {{verify}} from './verify-api.mjs'; verify(api);", cwd=scratch)
        elif channel == "python":
            venv = scratch / "consumer"
            run("uv", "venv", venv)
            python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            run("uv", "pip", "install", "--python", python, f"{NAME}=={VERSION}")
            run(python, ROOT / "py/scripts/conformance.py", "--installed", cwd=scratch)
            run(python, "-m", NAME, "--help", cwd=scratch)


CHECKS = {
    "metadata": metadata,
    "javascript": javascript,
    "js-package": js_package,
    "js-pnpm": lambda: js_manager("pnpm"),
    "js-yarn": lambda: js_manager("yarn"),
    "js-bun": lambda: js_manager("bun"),
    "python-package": python_package,
    "typst-package": typst_package,
    "typst-conformance": typst_conformance,
    "typst-family-preview": typst_family_preview,
    "rust-package": rust_package,
    "rust-dependencies": rust_dependencies,
    "resolve-dependencies": resolve_dependencies,
    "published-npm": lambda: published("npm"),
    "published-jsr": lambda: published("jsr"),
    "published-python": lambda: published("python"),
}

TOOLS = {
    "typst-family-preview": [("python3", "--version"), ("uv", "--version")],
    "metadata": [("python3", "--version")],
    "javascript": [("node", "--version"), ("bun", "--version")],
    "js-package": [("node", "--version"), ("bun", "--version"), ("npm", "--version"), ("deno", "--version")],
    "python-package": [("python3", "--version"), ("uv", "--version")],
    "typst-package": [("python3", "--version"), ("uv", "--version")],
    "typst-conformance": [("python3", "--version"), ("uv", "--version")],
    "rust-package": [("rustc", "--version"), ("cargo", "--version")],
    "rust-dependencies": [("rustc", "--version"), ("cargo", "--version")],
    "resolve-dependencies": [("cargo", "--version"), ("bun", "--version")],
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=CHECKS)
    arguments = parser.parse_args()
    started = time.monotonic()
    for command in TOOLS.get(arguments.check, []):
        run(*command)
    if arguments.check in {"metadata", "javascript", "js-package", "js-pnpm", "js-yarn", "js-bun", "python-package", "typst-package", "typst-conformance", "resolve-dependencies"}:
        # Build tools write generated files and dependency trees. Keep ccid's
        # verified input tree unchanged so successful Rust freshness is reusable.
        with tempfile.TemporaryDirectory(prefix=f"{NAME}-check-") as temporary:
            source = Path(temporary) / NAME
            shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(".git", "target", "node_modules", "dist"))
            ROOT = source
            JS = ROOT / "js" / "@corbet-foss" / NAME
            CHECKS[arguments.check]()
    else:
        CHECKS[arguments.check]()
    print(json.dumps({"check": arguments.check, "status": "passed", "seconds": round(time.monotonic() - started, 3)}))
