"""Vendor exact sibling Typst sources and record their content identities.

Run with an explicit directory containing cnice/cdate/cink checkouts.
This copies source assets only; it does not build packages or change versions.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tomllib

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("family_root", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
vendor = root / "typst/vendor"
previous = json.loads((vendor / "manifest.json").read_text())
manifest = {}
for name in ("cnice", "cdate", "cink"):
    source = args.family_root / name
    crate = tomllib.loads((source / "Cargo.toml").read_text())
    paths = sorted((source / "typst").rglob("*.typ"))
    if name in ("cnice", "cink"):
        # greet.typ reads its title table and ink.typ its defaults at
        # runtime; vendor those tables alongside.
        paths.extend(sorted((source / "tables").rglob("*.json")))
    paths.extend(sorted((source / "LICENSES").glob("*")))
    files = {}
    for path in paths:
        relative = path.relative_to(source)
        target = vendor / name / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        files[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    # Remove only obsolete generated files previously declared by this manifest.
    for obsolete in previous.get(name, {}).get("files", {}).keys() - files.keys():
        relative = Path(obsolete)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid previous vendor path")
        (vendor / name / relative).unlink(missing_ok=True)
    manifest[name] = {"repository": crate["package"]["repository"],
                      "version": crate["package"]["version"], "files": files}
(vendor / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Vendored Typst family sources with SHA-256 identities")
