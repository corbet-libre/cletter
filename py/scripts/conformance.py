"""Run canonical vectors against either the source port or an installed wheel."""
import base64
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if "--installed" not in sys.argv:
    sys.path.insert(0, str(ROOT / "py"))
api = importlib.import_module("cletter")

ARGUMENTS = {
    "salutation_last_name": ["input"],
    "salutation_honorific": ["locale", "input"],
    "salutation_titles": ["locale", "input"],
    "salutation_surname": ["locale", "input"],
    "salutation_supported": ["locale"],
    "recipient_salutation_warning": ["location", "input"],
    "honorific_warning": ["location", "locale", "input"],
    "closing": ["locale", "override"], "available_locales": [],
    "long_date": ["locale", "year", "month", "day"],
    "medium_date": ["locale", "year", "month", "day"],
    "short_date": ["locale", "year", "month", "day"],
    "month_year": ["locale", "year", "month"],
    "supported_formats": [], "normalize": ["input"],
    "exceeds_limits": ["image", "max_pixels"], "scale_to_fit": ["image", "max_pixels"],
    "signature_size": ["image", "height_pt", "max_width_pt"],
    "image_snippet": ["path", "height_pt", "width_pt"],
    "resolve_locale": ["language", "location"],
    "normalize_locale_id": ["input"], "normalize_language": ["input"], "country_from_location": ["input"],
    "orthography_replacements": ["locale"], "orthography_issues": ["locale", "text"],
    "opening": ["locale", "person", "override"],
    "subject": ["locale", "title", "prefix_override"],
    "salutation": ["locale", "person"], "apply_ortho": ["locale", "text"],
    "warnings": ["location", "locale", "person"],
}

files = sorted((ROOT / "tests/vectors").glob("*.json"))
assert files, "No conformance vectors"
count = 0
for file in files:
    for vector in json.loads(file.read_text(encoding="utf-8")):
        name = vector["fn"]
        values = dict(vector)
        if "fixture" in vector:
            values["input"] = base64.b64encode((ROOT / "tests/fixtures" / vector["fixture"]).read_bytes()).decode("ascii")
            if name != "normalize":
                values["image"] = api.normalize(values["input"])
        fn = getattr(api, name)
        actual = fn(*(values.get(key) for key in ARGUMENTS[name]))
        if name == "normalize" and actual is not None:
            actual = {key: getattr(actual, key) for key in ("mime", "width", "height")}
        if isinstance(actual, tuple):
            actual = list(actual)
        if actual != vector["expected"]:
            raise AssertionError(f"{file.name} :: {vector['name']}: {actual!r} != {vector['expected']!r}")
        count += 1
print(f"Python cletter: {count} vectors passed across {len(files)} files")
