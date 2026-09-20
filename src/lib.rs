//! Locale-correct business correspondence, composed from focused units.
//!
//! `cletter` is the front door: it re-exports [`cnice`] (salutations and
//! valedictions via `cnice::greet` and `cnice::farewell`), [`cink`]
//! (signature images) and [`cdate`]
//! (date formats), and adds what only makes sense together — locale
//! resolution, openings, subjects, orthography, and advisories.
//!
//! The locale tables live as data in `tables/*.json` (see
//! `tables/README.md`); `tests/vectors/*.json` is the executable contract
//! every language port runs. The Typst module in `typst/` derives from the
//! same tables.
//!
//! One locale per document (BCP 47). Unknown locales fall back through the
//! base language to English. Explicit overrides always win — tables supply
//! defaults, never commands. Same input always yields the same output: no
//! models, no I/O.

pub use cdate::{is_valid_date, long_date, medium_date, month_year, short_date};
pub use cink::{
    DecodedImage, ImageMime, default_max_pixels, exceeds_limits, image_snippet, normalize,
    scale_to_fit, signature_size, supported_formats,
};
pub use cnice::farewell::{available_locales, closing};
pub use cnice::greet::{
    honorific_warning, is_supported as salutation_supported, recipient_salutation_warning,
    salutation_honorific, salutation_last_name, salutation_surname, salutation_titles,
};

use std::collections::{HashMap, HashSet};
use std::sync::LazyLock;

#[derive(serde::Deserialize)]
struct LocaleEntry {
    formal: String,
    named: String,
    subject_prefix: String,
    subject_unsolicited: String,
    use_ss: bool,
}

#[derive(serde::Deserialize)]
struct LocalesFile {
    locales: HashMap<String, LocaleEntry>,
    supported: HashSet<String>,
    fallback: String,
    variants: HashMap<String, HashMap<String, String>>,
    orthography_replacements: Vec<[String; 2]>,
}

#[derive(serde::Deserialize)]
struct CountriesFile {
    #[serde(deserialize_with = "ordered_keywords")]
    keywords: Vec<(String, String)>,
    cantons: HashSet<String>,
}

// Country aliases have the same declaration-order priority in every port.
// Deserializing straight into a HashMap would randomize ambiguous matches.
fn ordered_keywords<'de, D>(deserializer: D) -> Result<Vec<(String, String)>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    struct KeywordsVisitor;

    impl<'de> serde::de::Visitor<'de> for KeywordsVisitor {
        type Value = Vec<(String, String)>;

        fn expecting(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            formatter.write_str("an ordered object of country keywords")
        }

        fn visit_map<M>(self, mut map: M) -> Result<Self::Value, M::Error>
        where
            M: serde::de::MapAccess<'de>,
        {
            let mut keywords = Vec::new();
            while let Some(entry) = map.next_entry()? {
                keywords.push(entry);
            }
            Ok(keywords)
        }
    }

    deserializer.deserialize_map(KeywordsVisitor)
}

static LOCALES: LazyLock<LocalesFile> = LazyLock::new(|| {
    serde_json::from_str(include_str!("../tables/locales.json"))
        .expect("tables/locales.json is valid")
});

static COUNTRIES: LazyLock<CountriesFile> = LazyLock::new(|| {
    serde_json::from_str(include_str!("../tables/countries.json"))
        .expect("tables/countries.json is valid")
});

fn base_language(code: &str) -> &str {
    code.split('-').next().unwrap_or(code)
}

/// Normalize an explicit locale ID's spelling without inferring a locale.
/// Trims only ASCII space, tab, LF, CR, VT and FF, replaces underscores with
/// hyphens and lowercases ASCII letters. Other characters are preserved.
/// Preserves all subtags, including variants absent from the correspondence
/// tables. This is not syntax or registry validation; callers validate their
/// supported shape separately. Empty input stays empty, and no region is added.
#[must_use]
pub fn normalize_locale_id(input: &str) -> String {
    input
        .trim_matches([' ', '\t', '\n', '\r', '\x0b', '\x0c'])
        .replace('_', "-")
        .to_ascii_lowercase()
}

/// Normalize a loose language string to a supported lowercase BCP 47 code.
/// Trims whitespace, accepts underscore separators and mixed case, and falls
/// back to the base language for unknown variants. Unknown languages yield `None`.
#[must_use]
pub fn normalize_language(input: &str) -> Option<String> {
    let lower = input.trim().replace('_', "-").to_ascii_lowercase();
    if LOCALES.supported.contains(&lower) {
        return Some(lower);
    }
    let base = base_language(&lower);
    LOCALES.supported.contains(base).then(|| base.to_owned())
}

/// Extract an uppercase ISO country code from a free-text location:
/// country keywords first, then Swiss cantons (`City, Canton` shape).
/// When multiple countries match, keyword declaration order in the canonical
/// table determines priority, consistently across language ports.
/// Matching lowercases Unicode-aware (locations are free text, unlike the
/// ASCII-only table tokens), mirroring the reference implementation.
#[must_use]
pub fn country_from_location(location: &str) -> Option<&'static str> {
    let lower = location.to_lowercase();
    let trimmed = lower.trim();
    if trimmed.is_empty() {
        return None;
    }
    for (keyword, code) in &COUNTRIES.keywords {
        if trimmed.contains(keyword.as_str()) {
            return Some(code.as_str());
        }
    }
    for part in trimmed.split([',', ';']).map(str::trim) {
        if COUNTRIES.cantons.contains(part) {
            return Some("CH");
        }
    }
    None
}

/// Resolve a language plus an optional free-text location to a BCP 47
/// locale: variant mapping through the country, base fallback, `en` when
/// nothing is recognized. No location preserves the normalized language.
#[must_use]
pub fn resolve_locale(language: Option<&str>, location: Option<&str>) -> String {
    let normalized = language
        .and_then(normalize_language)
        .unwrap_or_else(|| "en".to_owned());
    let base = base_language(&normalized).to_owned();
    let Some(country) = location.and_then(country_from_location) else {
        return normalized;
    };
    LOCALES
        .variants
        .get(&base)
        .and_then(|variants| variants.get(country))
        .cloned()
        .unwrap_or(base)
}

/// Resolve a lowercase table key: case-insensitive exact code, base language,
/// then English fallback. All stored and returned locale IDs are lowercase.
fn resolve_key(locale: &str) -> &'static str {
    let lower = locale.to_ascii_lowercase();
    LOCALES
        .locales
        .get_key_value(lower.as_str())
        .or_else(|| LOCALES.locales.get_key_value(base_language(&lower)))
        .map_or(LOCALES.fallback.as_str(), |(key, _)| key.as_str())
}

/// Opening line: when a name is given for a locale covered by the uniform
/// salutation renderer, the name is parsed and rendered the same way as
/// [`salutation`]; otherwise the `named` template is filled verbatim, or the
/// formal address when no name is given. An explicit override always wins.
#[must_use]
pub fn opening(locale: &str, name: Option<&str>, override_opening: Option<&str>) -> String {
    if let Some(custom) = override_opening {
        return custom.to_owned();
    }
    if let Some(name) = name.map(str::trim).filter(|name| !name.is_empty()) {
        if cnice::greet::is_supported(locale) {
            return cnice::greet::salutation(locale, name);
        }
        let entry = &LOCALES.locales[resolve_key(locale)];
        return entry.named.replace("{name}", name);
    }
    LOCALES.locales[resolve_key(locale)].formal.clone()
}

/// Subject line: prefix plus title, or the unsolicited-subject default when
/// no title is known. The override replaces the prefix only, mirroring how
/// per-workspace subject choices compose.
#[must_use]
pub fn subject(locale: &str, title: Option<&str>, prefix_override: Option<&str>) -> String {
    let entry = &LOCALES.locales[resolve_key(locale)];
    match title.map(str::trim).filter(|title| !title.is_empty()) {
        Some(title) => format!(
            "{} {title}",
            prefix_override.unwrap_or(&entry.subject_prefix)
        ),
        None => entry.subject_unsolicited.clone(),
    }
}

/// Locale-correct salutation through the uniform renderer for every locale
/// it covers (no per-language branch: coverage is data in the salutation
/// tables); all other locales resolve the opening template.
#[must_use]
pub fn salutation(locale: &str, name: &str) -> String {
    if cnice::greet::is_supported(locale) {
        cnice::greet::salutation(locale, name)
    } else {
        opening(locale, Some(name), None)
    }
}

/// Literal orthography replacements for the locale, in table order.
/// An empty slice means no substitutions. This is spelling data, not a full
/// grammar checker; the caller owns the boundary between prose and source text.
#[must_use]
pub fn orthography_replacements(locale: &str) -> &'static [[String; 2]] {
    if LOCALES.locales[resolve_key(locale)].use_ss {
        &LOCALES.orthography_replacements
    } else {
        &[]
    }
}

/// Non-mutating diagnostics: return each applicable source/replacement pair
/// found in the text, once, in table order. Pass generated prose only; names,
/// quotations, URLs and exact source material must be excluded by the caller.
#[must_use]
pub fn orthography_issues(locale: &str, text: &str) -> Vec<&'static [String; 2]> {
    orthography_replacements(locale)
        .iter()
        .filter(|pair| text.contains(pair[0].as_str()))
        .collect()
}

/// Apply the locale's literal spelling substitutions to caller-selected prose.
/// Swiss and Liechtenstein German replace ß with ss and ẞ with SS. This explicit
/// helper cannot recognize protected names, quotations, URLs or source material;
/// exclude them before calling, or use [`orthography_issues`] without mutation.
/// Opening, subject, closing and user overrides are never transformed implicitly.
#[must_use]
pub fn apply_ortho(locale: &str, text: &str) -> String {
    orthography_replacements(locale)
        .iter()
        .fold(text.to_owned(), |text, pair| {
            text.replace(&pair[0], &pair[1])
        })
}

/// Non-blocking advisories for a recipient name: the missing-name warning
/// in every locale, the honorific warning wherever the uniform renderer
/// applies. Empty means the record is clean.
#[must_use]
pub fn warnings(location: &str, locale: &str, name: &str) -> Vec<String> {
    let mut out = Vec::new();
    if let Some(warning) = recipient_salutation_warning(location, name) {
        out.push(warning);
    }
    if cnice::greet::is_supported(locale)
        && let Some(warning) = honorific_warning(location, locale, name)
    {
        out.push(warning);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tables_schema() {
        assert!(!LOCALES.locales.is_empty(), "table must not be empty");
        assert!(
            LOCALES.locales.contains_key(LOCALES.fallback.as_str()),
            "fallback must be a known locale"
        );
        for (key, entry) in &LOCALES.locales {
            assert_eq!(
                key,
                &key.to_ascii_lowercase(),
                "locale ID must be lowercase"
            );
            assert!(
                !entry.formal.is_empty(),
                "formal must not be empty: {key:?}"
            );
            // Locales covered by the uniform salutation renderer keep a
            // formal duplicate here: named rendering is owned by cnice
            // data, never by a per-language branch in code.
            if !cnice::greet::is_supported(key) {
                assert!(
                    entry.named.contains("{name}"),
                    "named template needs {{name}}: {key:?}"
                );
            }
            assert!(
                !entry.subject_prefix.is_empty(),
                "subject prefix must not be empty: {key:?}"
            );
            assert!(
                !entry.subject_unsolicited.is_empty(),
                "unsolicited subject must not be empty: {key:?}"
            );
        }
        for code in &LOCALES.supported {
            assert!(!code.is_empty(), "supported code must not be empty");
            assert_eq!(
                code,
                &code.to_ascii_lowercase(),
                "supported ID must be lowercase"
            );
        }
        for (keyword, _) in &COUNTRIES.keywords {
            assert_eq!(
                keyword,
                &keyword.to_ascii_lowercase(),
                "keyword must be lowercase: {keyword:?}"
            );
        }
    }

    #[test]
    fn ambiguous_countries_follow_canonical_keyword_order() {
        // Text order does not replace the table's established priority.
        assert_eq!(country_from_location("Germany / Switzerland"), Some("CH"));
        assert_eq!(country_from_location("Switzerland / Germany"), Some("CH"));
        assert_eq!(country_from_location("Austria / Germany"), Some("DE"));
        assert_eq!(
            resolve_locale(Some("de"), Some("Germany / Switzerland")),
            "de-ch"
        );
    }

    #[test]
    fn country_deserialization_keeps_declared_order() {
        let countries: CountriesFile =
            serde_json::from_str(r#"{"keywords":{"zulu":"CH","alpha":"DE"},"cantons":[]}"#)
                .expect("valid country table");
        assert_eq!(
            countries.keywords,
            vec![
                ("zulu".to_owned(), "CH".to_owned()),
                ("alpha".to_owned(), "DE".to_owned()),
            ]
        );
    }

    fn run_vector(file: &std::path::Path, vector: &serde_json::Value) {
        let name = vector["name"].as_str().unwrap_or("<unnamed>");
        let context = format!("{} :: {name}", file.display());
        let actual: serde_json::Value = match vector["fn"].as_str().unwrap_or("") {
            "normalize_locale_id" => {
                normalize_locale_id(vector["input"].as_str().unwrap_or("")).into()
            }
            "normalize_language" => {
                normalize_language(vector["input"].as_str().unwrap_or("")).into()
            }
            "country_from_location" => {
                country_from_location(vector["input"].as_str().unwrap_or("")).into()
            }
            "orthography_replacements" => {
                serde_json::to_value(orthography_replacements(vector["locale"].as_str().unwrap()))
                    .unwrap()
            }
            "orthography_issues" => serde_json::to_value(orthography_issues(
                vector["locale"].as_str().unwrap(),
                vector["text"].as_str().unwrap(),
            ))
            .unwrap(),
            "resolve_locale" => {
                let language = vector.get("language").and_then(serde_json::Value::as_str);
                let location = vector.get("location").and_then(serde_json::Value::as_str);
                serde_json::Value::String(resolve_locale(language, location))
            }
            "opening" => {
                let locale = vector["locale"].as_str().expect("vector needs locale");
                let who = vector.get("person").and_then(serde_json::Value::as_str);
                let override_opening = vector.get("override").and_then(serde_json::Value::as_str);
                serde_json::Value::String(opening(locale, who, override_opening))
            }
            "subject" => {
                let locale = vector["locale"].as_str().expect("vector needs locale");
                let title = vector.get("title").and_then(serde_json::Value::as_str);
                let prefix = vector
                    .get("prefix_override")
                    .and_then(serde_json::Value::as_str);
                serde_json::Value::String(subject(locale, title, prefix))
            }
            "salutation" => {
                let locale = vector["locale"].as_str().expect("vector needs locale");
                let who = vector
                    .get("person")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("");
                serde_json::Value::String(salutation(locale, who))
            }
            "apply_ortho" => {
                let locale = vector["locale"].as_str().expect("vector needs locale");
                let text = vector["text"].as_str().unwrap_or("");
                serde_json::Value::String(apply_ortho(locale, text))
            }
            "warnings" => {
                let location = vector["location"].as_str().expect("vector needs location");
                let locale = vector["locale"].as_str().expect("vector needs locale");
                let who = vector
                    .get("person")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("");
                serde_json::Value::Array(
                    warnings(location, locale, who)
                        .iter()
                        .map(|warning| serde_json::Value::String(warning.clone()))
                        .collect(),
                )
            }
            "long_date" | "medium_date" | "short_date" => {
                let locale = vector["locale"].as_str().expect("vector needs locale");
                let year = i32::try_from(vector["year"].as_i64().expect("vector needs year"))
                    .expect("vector year fits i32");
                let month = u32::try_from(vector["month"].as_u64().expect("vector needs month"))
                    .expect("vector month fits u32");
                let day = u32::try_from(
                    vector
                        .get("day")
                        .and_then(serde_json::Value::as_u64)
                        .unwrap_or(1),
                )
                .expect("vector day fits u32");
                match vector["fn"].as_str().unwrap_or("") {
                    "long_date" => long_date(locale, year, month, day).into(),
                    "medium_date" => medium_date(locale, year, month, day).into(),
                    _ => short_date(locale, year, month, day).into(),
                }
            }
            "month_year" => {
                let locale = vector["locale"].as_str().expect("vector needs locale");
                let year = i32::try_from(vector["year"].as_i64().expect("vector needs year"))
                    .expect("vector year fits i32");
                let month = u32::try_from(vector["month"].as_u64().expect("vector needs month"))
                    .expect("vector month fits u32");
                month_year(locale, year, month).into()
            }
            other => panic!("{context}: unknown fn {other:?}"),
        };
        let expected = vector
            .get("expected")
            .cloned()
            .unwrap_or(serde_json::Value::Null);
        assert_eq!(actual, expected, "{context}");
    }

    #[test]
    fn conformance_vectors() {
        let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/vectors");
        let mut files: Vec<std::path::PathBuf> = std::fs::read_dir(&dir)
            .expect("tests/vectors exists")
            .map(|entry| entry.expect("readable entry").path())
            .collect();
        files.sort();
        assert!(!files.is_empty(), "no vector files in tests/vectors");
        let mut count = 0;
        for file in &files {
            let raw = std::fs::read_to_string(file).expect("vector file is readable");
            let vectors: Vec<serde_json::Value> =
                serde_json::from_str(&raw).expect("vector file is valid JSON");
            for vector in &vectors {
                run_vector(file, vector);
                count += 1;
            }
        }
        assert!(count > 0, "no vectors ran");
    }
}
