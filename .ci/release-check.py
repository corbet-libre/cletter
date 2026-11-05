#!/usr/bin/env python3
"""Check the release adapter contract without builds, network or secrets."""
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


def workflow_jobs(source):
    """Split a workflow's top-level jobs into {name: block} without a YAML parser."""
    body = source.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([A-Za-z0-9_-]+):\n", body, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def main():
    paths = [".ci/publish.py", ".ci/release-check.py", ".ci/ccid.toml",
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
    hosted = files[".github/workflows/release.yml"]
    pins = re.findall(r"^\s+CCID_REVISION:\s*['\"]?([0-9a-f]{40})['\"]?\s*$", hosted, re.M)
    require(len(pins) == 1, "Hosted release must pin a reviewed publisher revision")
    require(hosted.count("repository: corbet-libs/ccid\n") == hosted.count("ref: ${{ env.CCID_REVISION }}\n") >= 1
            and "ref: " not in hosted.replace("ref: ${{ env.CCID_REVISION }}", ""),
            "Hosted checkout differs from the pinned publisher")
    # One pushed vX.Y.Z tag is the release trigger; dispatch re-runs or rehearses.
    require(re.search(r"^on:\n  push:\n    tags: \['v\*\.\*\.\*'\]\n  workflow_dispatch:\n", hosted, re.M)
            and "branches:" not in hosted and "pull_request" not in hosted
            and "github.event.repository.private == false" in hosted, "Hosted release requires public tagged source")
    require("secrets." not in hosted and all(name not in hosted for name in ("NPM_TOKEN", "JSR_TOKEN", "PYPI_TOKEN")),
            "Long-lived registry secrets belong only to the Crow publication step")
    jobs = workflow_jobs(hosted)
    require(set(jobs) == {"prepare", "bundle", "publish"}, "Unexpected hosted release jobs")
    require("uses: ./.github/workflows/ci.yml\n" in jobs["prepare"] and not re.search(r":\s*write\b", jobs["prepare"])
            and "id-token" not in jobs["bundle"] and "contents: write" in jobs["bundle"],
            "Preparation and bundling must run without registry credentials")
    require("id-token: write" in jobs["publish"] and hosted.count("id-token") == 1,
            "Only the publication job may request OIDC tokens")
    publish = jobs["publish"]
    require("RELEASE_CARGO_AUTH: trusted" in publish and "steps.authentication.outputs.token" in publish
            and "RELEASE_JSR_AUTH: trusted" in publish, "Hosted publication must use the Cargo and JSR OIDC routes")
    # npm and PyPI stay operator uploads until their trusted publisher rules exist.
    require(all(name not in hosted for name in ("RELEASE_NPM_AUTH", "RELEASE_PYPI_AUTH")),
            "npm and PyPI have no trusted publisher rule yet")
    require(publish.count("python3 .ci/publish.py publish") == 2
            and all("RELEASE_CHANNELS: " + channel + "\n" in publish for channel in ("cargo", "jsr")),
            "Each hosted upload must select exactly one OIDC registry")
    checks = files[".github/workflows/ci.yml"]
    require("'release'" in checks and "release-config) python3 .ci/release-check.py" in checks,
            "Hosted selected checks must route release configuration separately from publication")
    require("workflow_call:" in checks and "secrets" not in checks and not re.search(r":\s*write\b", checks),
            "Selected checks must stay a credential-free reusable preparation workflow")
    for path in (".github/workflows/release.yml", ".github/workflows/ci.yml"):
        source = files[path]
        # Only release.yml's tag trigger may start work automatically.
        automatic = re.findall(r"^ +(?:push|pull_request\w*|schedule):", source, re.M)
        require(automatic == (["  push:"] if path == ".github/workflows/release.yml" else []),
                "Only a pushed release tag may start an adapter automatically")
        for action in re.findall(r"^\s+uses:\s*(\S+)", source, re.M):
            require(action == "./.github/workflows/ci.yml" or re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", action),
                    "Hosted actions require exact revisions")
        check_shell_blocks(source, path)
    actionlint = shutil.which("actionlint")
    if not actionlint:
        candidates = sorted(Path("/nix/store").glob("*-actionlint-*/bin/actionlint"))
        actionlint = str(candidates[-1]) if candidates else None
    require(actionlint is not None, "Actionlint is required; use the provisioned Crow tool or hosted setup")
    version = subprocess.check_output([actionlint, "-version"], text=True).strip()
    subprocess.run([actionlint, ".github/workflows/ci.yml", ".github/workflows/release.yml"], cwd=ROOT, check=True)
    print(json.dumps({"repository": repository, "publisher_revision": pins[0],
                      "checks": ["python syntax", "shell syntax", "release contract"],
                      "actionlint": {"path": actionlint, "version": version, "status": "passed"},
                      "files": {path: hashlib.sha256(value.encode()).hexdigest() for path, value in files.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
