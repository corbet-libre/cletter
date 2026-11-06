"""Build a Typst archive and compile an installed-package example.

Run with the development dependency typst==0.15.0. Package contents come only
from the repository; installation verification uses a fresh local namespace.
The cletter sources import cnice, cdate and cink as `@preview` packages at
exact versions. Verification installs those from sibling checkouts in
FAMILY_ROOT (default: CCID_SIBLINGS_DIR when a CI runner staged the siblings,
otherwise the parent directory), whose versions must match.

Usage: python scripts/package-typst.py [FAMILY_ROOT]
"""
from pathlib import Path
import gzip
import hashlib
import io
import re
import os
import shutil
import sys
import tarfile
import tempfile
import tomllib

import typst

ROOT = Path(__file__).resolve().parents[1]
# An explicit argument wins; then CCID_SIBLINGS_DIR (the siblings a CI runner staged for this job); then the parent directory.
FAMILY_ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CCID_SIBLINGS_DIR") or ROOT.parent).resolve()
manifest = tomllib.loads((ROOT / "typst.toml").read_text())["package"]
name, version = manifest["name"], manifest["version"]
examples = {
    "cgreet": '#assert(api.de-salutation("Frau Dr. Müller", region: "ch") == "Sehr geehrte Frau Dr. Müller")',
    "cfarewell": '#assert(api.closing("de-ch") == "Freundliche Grüsse")',
    "cdate": '#assert(api.long-date("en-GB", 2026, 9, 7) == "7 September 2026")\n#assert(api.is-valid-date(2026, 9, 7.5) == false)\n#assert(api.month-year("de", 2026.5, 9) == none)\n#assert(api.short-date("de", -1, 9, 7) == "07.09.99")',
    "cink": '#api.signature-image(read("signature.svg", encoding: none), 20)',
    "cletter": '#assert(api.normalize-locale-id(" EN_CH ") == "en-ch")\n#assert(api.salutation("de-ch", "Frau Dr. Müller") == "Sehr geehrte Frau Dr. Müller")\n#assert(api.long-date("en-GB", 2026, 9, 7) == "7 September 2026")\n#assert(api.is-valid-date(2026, 9, 7.5) == false)\n#assert(api.short-date("de", -1, 9, 7) == "07.09.99")\n#assert(api.closing("DE-LI") == "Freundliche Grüsse")\n#assert(api.apply-ortho("de-li", "Grüße GROẞ") == "Grüsse GROSS")\n#api.signature-image(read("signature.svg", encoding: none), 20)',
}

with tempfile.TemporaryDirectory(prefix=f"{name}-typst-") as tmp:
    stage = Path(tmp) / "source"
    stage.mkdir()
    for item in ("typst.toml", "README.md", "LICENSE", "LICENSE.md", "LICENSES", "typst", "tables"):
        source = ROOT / item
        if source.is_dir():
            shutil.copytree(source, stage / item)
        elif source.is_file():
            shutil.copy2(source, stage / item)
        else:
            raise FileNotFoundError(source)
    archive_bytes = io.BytesIO()
    with gzip.GzipFile(fileobj=archive_bytes, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as archive:
            for path in sorted(stage.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(stage).as_posix()
                data = path.read_bytes()
                info = tarfile.TarInfo(relative)
                info.size, info.mode, info.mtime = len(data), 0o644, 0
                archive.addfile(info, io.BytesIO(data))
    packed = archive_bytes.getvalue()
    packages = Path(tmp) / "packages"
    installed = packages / "local" / name / version
    installed.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(packed), mode="r:gz") as archive:
        archive.extractall(installed, filter="data")
    # Install the exact family packages the sources import, offline.
    imports = sorted({
        match.groups()
        for path in (stage / "typst").rglob("*.typ")
        for match in re.finditer(r'"@preview/([a-z][a-z0-9-]*):([0-9]+\.[0-9]+\.[0-9]+)"', path.read_text())
    })
    for dependency, required in imports:
        source = FAMILY_ROOT / dependency
        found = tomllib.loads((source / "typst.toml").read_text())["package"]["version"]
        if found != required:
            raise ValueError(f"{name} imports @preview/{dependency}:{required}, {source} is {found}")
        target = packages / "preview" / dependency / required
        target.mkdir(parents=True)
        shutil.copy2(source / "typst.toml", target / "typst.toml")
        for item in ("typst", "tables"):
            if (source / item).is_dir():
                shutil.copytree(source / item, target / item)
    example = Path(tmp) / "main.typ"
    example.write_text(
        f'#import "@local/{name}:{version}" as api\n'
        + examples[name] + '\nPackage import verified.\n', encoding="utf-8"
    )
    (Path(tmp) / "signature.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="20">'
        '<path d="M0 10L80 10" stroke="black"/></svg>'
    )
    pdf = typst.compile(str(example), root=tmp, package_path=str(packages))
    assert pdf.startswith(b"%PDF"), "Compiler did not produce a PDF"
    output = ROOT / "dist" / f"{name}-{version}-typst.tar.gz"
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(packed)
    print(f"Typst installed import verified: {output.name} sha256={hashlib.sha256(packed).hexdigest()}")
