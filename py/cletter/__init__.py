"""Locale-correct correspondence, composed from three focused libraries."""

import re
from cdate import is_valid_date, long_date, medium_date, month_year, short_date
from cnice.farewell import available_locales, closing
from cnice.greet import (honorific_warning, recipient_salutation_warning,
                         salutation as _cnice_salutation,
                         salutation_honorific, salutation_last_name, salutation_surname,
                         salutation_titles)
from cnice.greet import is_supported as salutation_supported
from cink import (DecodedImage, default_max_pixels, exceeds_limits, image_snippet,
                  normalize, scale_to_fit, signature_size, supported_formats)
from ._tables import TABLES

_LOCALES = TABLES["locales"]
_COUNTRIES = TABLES["countries"]
__all__ = ["normalize_locale_id", "normalize_language", "country_from_location", "resolve_locale",
           "opening", "subject", "salutation", "apply_ortho", "orthography_replacements", "orthography_issues", "warnings",
           "is_valid_date", "long_date", "medium_date", "month_year", "short_date",
           "available_locales", "closing", "honorific_warning",
           "recipient_salutation_warning", "salutation_supported",
           "salutation_honorific", "salutation_last_name", "salutation_surname",
           "salutation_titles", "default_max_pixels", "exceeds_limits", "image_snippet",
           "normalize", "scale_to_fit", "signature_size", "supported_formats"]


def normalize_locale_id(value: str) -> str:
    """Normalize locale spelling without inference, fallback or validation.

    Trim only ASCII space, tab, LF, CR, VT and FF; replace underscores with
    hyphens and lowercase ASCII letters. Preserve other characters.
    Keep all subtags, even outside the correspondence tables; empty stays empty.
    Callers validate their supported identifier shape separately.
    """
    return value.strip(" \t\n\r\v\f").replace("_", "-").translate(str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))


def normalize_language(value: str) -> str | None:
    """Normalize mixed case and underscores to a supported lowercase locale ID."""
    lower = value.strip().replace("_", "-").lower()
    if lower in _LOCALES["supported"]:
        return lower
    base = lower.split("-", 1)[0]
    return base if base in _LOCALES["supported"] else None


def country_from_location(location: str) -> str | None:
    """Look up country keywords, then Swiss canton names in a location."""
    text = location.lower().strip()
    if not text:
        return None
    for keyword, code in _COUNTRIES["keywords"].items():
        if keyword in text:
            return code
    for part in re.split("[,;]", text):
        if part.strip() in _COUNTRIES["cantons"]:
            return "CH"
    return None


def resolve_locale(language: str | None = None, location: str | None = None) -> str:
    """Resolve language and an optional location into one document locale."""
    normalized = normalize_language(language) if language is not None else None
    normalized = normalized or "en"
    base = normalized.split("-", 1)[0]
    country = country_from_location(location) if location is not None else None
    return normalized if country is None else _LOCALES["variants"].get(base, {}).get(country, base)


def _entry(locale: str) -> dict:
    lower = locale.lower()
    key = lower if lower in _LOCALES["locales"] else lower.split("-", 1)[0]
    if key not in _LOCALES["locales"]:
        key = _LOCALES["fallback"]
    return _LOCALES["locales"][key]


def opening(locale: str, name: str | None = None, override_opening: str | None = None) -> str:
    """Named opening or formal address; an explicit override always wins.

    When a name is given for a locale covered by the uniform salutation
    renderer, the name is parsed and rendered the same way as salutation();
    otherwise the named template is filled verbatim, or the formal address
    when no name is given.
    """
    if override_opening is not None:
        return override_opening
    clean = name.strip() if name is not None else ""
    if clean:
        if salutation_supported(locale):
            return _cnice_salutation(locale, clean)
        return _entry(locale)["named"].replace("{name}", clean)
    return _entry(locale)["formal"]


def subject(locale: str, title: str | None = None, prefix_override: str | None = None) -> str:
    """Subject prefix plus title, or the locale's unsolicited-application subject."""
    entry = _entry(locale)
    clean = title.strip() if title is not None else ""
    prefix = entry["subject_prefix"] if prefix_override is None else prefix_override
    return prefix + " " + clean if clean else entry["subject_unsolicited"]


def salutation(locale: str, name: str) -> str:
    """Locale-correct salutation through the uniform renderer where covered, else the opening template."""
    if salutation_supported(locale):
        return _cnice_salutation(locale, name)
    return opening(locale, name)


def orthography_replacements(locale: str) -> list[list[str]]:
    """Return a copy of the locale's literal replacement pairs in table order."""
    return [pair.copy() for pair in _LOCALES["orthography_replacements"]] if _entry(locale)["use_ss"] else []


def orthography_issues(locale: str, text: str) -> list[list[str]]:
    """Report applicable pairs once, without changing caller-selected prose."""
    return [pair for pair in orthography_replacements(locale) if pair[0] in text]


def apply_ortho(locale: str, text: str) -> str:
    """Apply spelling substitutions to prose; callers exclude names/quotes/URLs/sources.

    Opening, subject, closing and overrides are never transformed implicitly.
    Use orthography_issues when a protected-content boundary is not available.
    """
    for source, replacement in orthography_replacements(locale):
        text = text.replace(source, replacement)
    return text


def warnings(location: str, locale: str, name: str) -> list[str]:
    """Nonblocking advisories: missing-name everywhere, honorific where the renderer applies."""
    items = [recipient_salutation_warning(location, name)]
    if salutation_supported(locale):
        items.append(honorific_warning(location, locale, name))
    return [item for item in items if item is not None]
