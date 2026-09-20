#!/usr/bin/env python3
"""Check the manual release adapter contract without builds, network or secrets."""
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import textwrap
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def check_shell_blocks(source, path):
    lines = source.splitlines()
    for index, line in enumerate(lines):
        match = re.fullmatch(r"( +)(?:run: \||- \|)", line)
        if not match:
            continue
        body = []
        for candidate in lines[index + 1:]:
            if candidate.strip() and len(candidate) - len(candidate.lstrip()) <= len(match[1]):
                break
            body.append(candidate)
        script = textwrap.dedent("\n".join(body)) + "\n"
        subprocess.run(["bash", "-n"], input=script, text=True, check=True)
        for embedded in re.findall(r"python3 - <<'PYTHON'\n(.*?)^PYTHON$", script, re.M | re.S):
            ast.parse(embedded, filename=path + ":python-heredoc")


def check_crow_secrets(source, package):
    sections = re.split(r"^  - name: ", source, flags=re.M)
    require("from_secret:" not in sections[0], "Shared release configuration must have no credentials")
    steps = dict(section.split("\n", 1) for section in sections[1:])
    expected = {"validate-release-selection", "inspect-prepared-packages", "release-status",
                "publish-cargo", "publish-npm", "publish-jsr", "publish-pypi"}
    require(len(sections) == len(expected) + 1 and set(steps) == expected, "Unexpected release credential boundaries")
    require("when:" not in steps["validate-release-selection"], "Release input validation must always run")
    for name, block in steps.items():
        secrets = re.findall(r"from_secret:\s*([A-Za-z0-9_]+)", block)
        expected_secrets = []
        if name == "release-status" or name.startswith("publish-"):
            expected_secrets.append(package + "_release_github_token")
        if name.startswith("publish-"):
            channel = name.removeprefix("publish-")
            expected_secrets.append(package + "_release_" + channel + "_token")
            require('RELEASE_OPERATION == "publish"' in block and 'RELEASE_CHANNELS == "' + channel + '"' in block,
                    "Publication credentials require compile-time operation/channel guards")
        elif name in {"inspect-prepared-packages", "release-status"}:
            operation = "inspect" if name == "inspect-prepared-packages" else "status"
            require('RELEASE_OPERATION == "' + operation + '"' in block, "Inspection/status operation guard is missing")
        require(sorted(secrets) == sorted(expected_secrets), "Step has unexpected or missing release credentials: " + name)
        if name != "validate-release-selection":
            require("when:" in block and "evaluate:" in block and "validate-release-selection" in block,
                    "Release executor must be compile-time guarded and depend on input validation")
            require(re.search(r"[&*]publisher-environment\b", block) and re.search(r"[&*]publisher-commands\b", block),
                    "Release executors must reuse the same verified publisher identity and commands")


def main():
    paths = [".ci/publish.py", ".ci/release-check.py", ".ci/ccid.toml", ".crow/release.yaml",
             ".github/workflows/release.yml", ".github/workflows/ci.yml"]
    files = {path: (ROOT / path).read_text() for path in paths}
    package = tomllib.loads((ROOT / "Cargo.toml").read_text())["package"]["name"]
    repository = "corbet-foss/" + package
    adapter = ast.parse(files[".ci/publish.py"], filename=".ci/publish.py")
    ast.parse(files[".ci/release-check.py"], filename=".ci/release-check.py")
    assignments = {node.targets[0].id: ast.literal_eval(node.value) for node in adapter.body
                   if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == "REPOSITORY"}
    require(assignments.get("REPOSITORY") == repository, "Publication adapter repository mismatch")
    require('"adapters/registry_publish.py"' in files[".ci/publish.py"], "Shared verified publisher resource is required")
    config = tomllib.loads(files[".ci/ccid.toml"])
    for selector, command in (("release", ".ci/publish.py"), ("release-config", ".ci/release-check.py")):
        require(config["checks"][selector] == {"kind": "commands", "commands": [["python3", command]]},
                "Unexpected manual publication selector command")
    crow, hosted = files[".crow/release.yaml"], files[".github/workflows/release.yml"]
    pins = [re.findall(r"^\s+CCID_REVISION:\s*['\"]?([0-9a-f]{40})['\"]?\s*$", value, re.M) for value in (crow, hosted)]
    require(len(pins[0]) == 1 and pins[0] == pins[1], "Release routes must pin the same reviewed publisher revision")
    require("ref: " + pins[0][0] in hosted, "Hosted checkout differs from the pinned publisher")
    require("event: manual" in crow and "branch: main" in crow and "--check release" in crow,
            "Crow publication must remain a manual main-branch release command")
    require("workflow_dispatch:" in hosted and "github.event.repository.private == false" in hosted
            and "github.ref == 'refs/heads/main'" in hosted, "Hosted release requires public main source")
    require("secrets." not in hosted and all(name not in hosted for name in ("NPM_TOKEN", "JSR_TOKEN", "PYPI_TOKEN")),
            "Long-lived registry secrets belong only to the Crow publication step")
    require("RELEASE_CARGO_AUTH: trusted" in hosted and "steps.authentication.outputs.token" in hosted
            and '"$RELEASE_CHANNELS" != cargo' in hosted, "Hosted publication must use the selected Cargo OIDC route")
    require("from_secret: " + package + "_release_pypi_token" in crow, "Crow PyPI route is missing")
    check_crow_secrets(crow, package)
    require("rustup" not in crow and "cargo build" not in crow and "cargo test" not in crow,
            "Credentialed Crow publication must not build products")
    checks = files[".github/workflows/ci.yml"]
    require("'release'" in checks and "release-config) python3 .ci/release-check.py" in checks,
            "Hosted selected checks must route release configuration separately from publication")
    for path in (".crow/release.yaml", ".github/workflows/release.yml", ".github/workflows/ci.yml"):
        source = files[path]
        require(not re.search(r"^\s+(?:push|pull_request):", source, re.M), "These adapters must remain manual")
        for action in re.findall(r"^\s+uses:\s*(\S+)", source, re.M):
            require(re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", action), "Hosted actions require exact revisions")
        check_shell_blocks(source, path)
    actionlint = shutil.which("actionlint")
    if not actionlint:
        candidates = sorted(Path("/nix/store").glob("*-actionlint-*/bin/actionlint"))
        actionlint = str(candidates[-1]) if candidates else None
    require(actionlint is not None, "Actionlint is required; use the provisioned Crow tool or hosted setup")
    version = subprocess.check_output([actionlint, "-version"], text=True).strip()
    subprocess.run([actionlint, ".github/workflows/ci.yml", ".github/workflows/release.yml"], cwd=ROOT, check=True)
    print(json.dumps({"repository": repository, "publisher_revision": pins[0][0],
                      "checks": ["python syntax", "shell syntax", "manual release contract"],
                      "actionlint": {"path": actionlint, "version": version, "status": "passed"},
                      "files": {path: hashlib.sha256(value.encode()).hexdigest() for path, value in files.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
