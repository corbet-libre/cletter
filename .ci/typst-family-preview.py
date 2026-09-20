"""Compile each prepared Universe package and its exact README examples."""
from pathlib import Path
import re
import sys
import tarfile
import tempfile
import tomllib

import typst

VERSION = tomllib.loads((Path(__file__).resolve().parents[1] / "Cargo.toml").read_text())["package"]["version"]
EXPECTED = {"cdate": "0.2.1", "cfarewell": "0.2.1", "cink": "0.1.4", "cletter": VERSION}
archives = [Path(value) for value in sys.argv[1:]]
if len(archives) != len(EXPECTED):
    raise ValueError("Expected exactly four prepared family archives")

with tempfile.TemporaryDirectory(prefix="cletter-preview-") as temporary:
    root = Path(temporary)
    packages = root / "packages"
    seen = set()
    examples = []
    for archive in archives:
        with tarfile.open(archive, "r:gz") as stream:
            members = stream.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)) or len(names) > 100:
                raise ValueError("Unexpected duplicate or excessive package contents")
            for member in members:
                path = Path(member.name)
                if (path.is_absolute() or ".." in path.parts or not member.isfile()
                        or member.size > 2_000_000):
                    raise ValueError("Unexpected preview package member")
            manifest = tomllib.loads(stream.extractfile("typst.toml").read().decode())["package"]
            name, version = manifest["name"], manifest["version"]
            if (EXPECTED.get(name) != version or name in seen
                    or manifest["license"] != "Apache-2.0" or "LICENSE" not in names):
                raise ValueError("Prepared package identity or license differs")
            seen.add(name)
            installed = packages / "preview" / name / version
            installed.mkdir(parents=True)
            stream.extractall(installed, filter="data")
        readme = (installed / "README.md").read_text()
        blocks = re.findall(r"(?ms)^```typst[ \t]*\n(.*?)^```[ \t]*$", readme)
        if not blocks or any(f'"@preview/{name}:{version}"' not in block for block in blocks):
            raise ValueError("Every README example must use its exact preview import")
        for index, block in enumerate(blocks):
            example = root / f"{name}-{index}.typ"
            example.write_text(block)
            examples.append(example)
    for example in examples:
        pdf = typst.compile(str(example), root=str(root), package_path=str(packages))
        if not pdf.startswith(b"%PDF"):
            raise ValueError("Preview example did not produce a PDF")
        print(f"Prepared preview README passed: {example.name}", flush=True)
    print(f"Verified {len(seen)} packages and {len(examples)} README examples", flush=True)
