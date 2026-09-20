"""Run canonical JSON vectors against the Typst ports with an existing compiler.

Usage: python3 scripts/typst-conformance.py FAMILY_ROOT [cletter cgreet ...]
Uses typst or tinymist already on PATH, or an installed Python typst module;
performs no installation.
"""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
libraries = sys.argv[2:] or ["cnice", "cdate", "cletter"]
compiler = shutil.which("typst") or shutil.which("tinymist")
if compiler:
    subprocess.run([compiler, "--version"], check=True)
else:
    try:
        import typst
        from importlib.metadata import version
    except ImportError:
        raise SystemExit("An existing typst/tinymist compiler or Python typst module is required") from None
    print(f"Python typst compiler: {version('typst')}", flush=True)
arguments = {
    "salutation_last_name": ["input"], "salutation_honorific": ["locale", "input"],
    "salutation_titles": ["locale", "input"], "salutation_surname": ["locale", "input"],
    "salutation": ["locale", "person"],
    "recipient_salutation_warning": ["location", "input"],
    "honorific_warning": ["location", "locale", "input"],
    "closing": ["locale", ("override", "override")], "available_locales": [],
    "long_date": ["locale", "year", "month", "day"],
    "medium_date": ["locale", "year", "month", "day"],
    "short_date": ["locale", "year", "month", "day"],
    "month_year": ["locale", "year", "month"], "is_supported": ["locale"],
    "is_valid_date": ["year", "month", "day"],
    "resolve_locale": [("language", "language"), ("location", "location")],
    "normalize_locale_id": ["input"], "normalize_language": ["input"], "country_from_location": ["input"],
    "opening": ["locale", ("name", "person"), ("override", "override")],
    "subject": ["locale", ("title", "title"), ("prefix-override", "prefix_override")],
    "apply_ortho": ["locale", "text"],
    "orthography_replacements": ["locale"], "orthography_issues": ["locale", "text"],
    "warnings": ["location", "locale", "person"],
}
# A library may expose several Typst modules (cnice keeps greet/farewell
# separate since both define different names; star-imports do not collide).
modules = {"cnice": ("greet", "farewell"), "cdate": ("date",), "cletter": ("letter",)}

def value(item):
    if item is None:
        return "none"
    if isinstance(item, str):
        # Typst uses braced Unicode escapes and has no JSON \b or \f escapes.
        escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
        return '"' + "".join(
            escapes.get(char, f"\\u{{{ord(char):x}}}" if ord(char) < 32 else char)
            for char in item
        ) + '"'
    if isinstance(item, list):
        return "(" + ",".join(map(value, item)) + ("," if item else "") + ")"
    return json.dumps(item, ensure_ascii=False)

for library in libraries:
    lines = [f'#import "/{library}/typst/{module}.typ": *' for module in modules[library]]
    count = 0
    for path in sorted((root / library / "tests/vectors").glob("*.json")):
        for vector in json.loads(path.read_text()):
            # cnice names its recipient arg "input", cletter "person".
            if vector["fn"] == "salutation" and "person" not in vector and "input" in vector:
                vector = {**vector, "person": vector["input"]}
            name = vector["fn"]
            fn = name.replace("_", "-")
            args = []
            for arg in arguments[name]:
                if isinstance(arg, tuple):
                    label, key = arg
                    if key in vector:
                        args.append(label + ": " + value(vector[key]))
                else:
                    args.append(value(vector.get(arg)))
            call = fn + "(" + ", ".join(args) + ")"
            context = value(path.name + " :: " + vector["name"])
            lines.append(f'#assert.eq({call}, {value(vector["expected"])}, message: {context})')
            count += 1
    if not count:
        raise RuntimeError(f"No vectors for {library}")
    with tempfile.TemporaryDirectory(prefix=".typst-conformance-", dir=root) as temp:
        entry = Path(temp) / "vectors.typ"
        entry.write_text("\n".join(lines) + "\n")
        if compiler:
            subprocess.run([compiler, "compile", "--root", str(root), str(entry), str(Path(temp) / "vectors.pdf")], check=True)
        else:
            pdf = typst.compile(str(entry), root=str(root))
            if not pdf.startswith(b"%PDF"):
                raise RuntimeError("Typst compiler did not produce a PDF")
    print(f"Typst {library}: {count} vectors passed", flush=True)
