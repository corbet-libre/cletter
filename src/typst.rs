//! The cletter Typst package and its family packages as embedded data, for
//! Rust hosts that run Typst in-process.
//!
//! The crate ships the same `typst.toml` and `typst/` sources that make up
//! the Typst package. `typst/letter.typ` imports the family packages
//! `@preview/cnice`, `@preview/cdate` and `@preview/cink`, which their own
//! crates embed. [`packages`] returns cletter together with those three, so
//! a host registers the complete correspondence family with one call
//! instead of downloading or vendoring copies:
//!
//! ```
//! let packages = cletter::typst::packages();
//! assert_eq!(packages[0].spec, cletter::typst::spec());
//! for package in &packages {
//!     for (path, bytes) in &package.files {
//!         // Register `bytes` at package-relative `path` for `package.spec`.
//!         assert!(!path.starts_with('/') && !bytes.is_empty());
//!     }
//! }
//! ```
//!
//! # Import versions
//!
//! A Typst import names one exact version, while Cargo may resolve a newer
//! semver compatible release of cnice, cdate or cink than the minimum that
//! cletter requires. The sources in `typst/` import those minimum versions,
//! which is what the standalone Typst package needs. [`packages`] rewrites
//! the version of every family import in cletter's sources to the release
//! Cargo actually linked (`cnice::typst::VERSION` and so on), so the Typst
//! code always runs against the exact packages registered beside it, and
//! Rust and Typst behave identically. [`FILES`] stays byte for byte equal
//! to the files on disk.

use std::borrow::Cow;

/// Package namespace used in Typst imports (`@preview/...`).
pub const NAMESPACE: &str = "preview";

/// Package name, as declared in `typst.toml`.
pub const NAME: &str = "cletter";

/// Package version; the Typst package follows the crate release line.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Package files as `(package-relative path, contents)`, sorted by path,
/// exactly as on disk. Paths use `/` separators; `typst.toml` names the
/// entrypoint. Hosts register [`packages`] instead, which pins the family
/// imports to the resolved crate versions.
pub const FILES: &[(&str, &[u8])] = &[
    ("typst.toml", include_bytes!("../typst.toml")),
    ("typst/README.md", include_bytes!("../typst/README.md")),
    (
        "typst/generated/tables.typ",
        include_bytes!("../typst/generated/tables.typ"),
    ),
    ("typst/letter.typ", include_bytes!("../typst/letter.typ")),
];

/// Package specification for Typst imports: `@preview/cletter:<version>`.
#[must_use]
pub fn spec() -> String {
    format!("@{NAMESPACE}/{NAME}:{VERSION}")
}

/// One Typst package, ready to register with a Typst world.
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub struct Package {
    /// Import specification, `@namespace/name:version`.
    pub spec: String,
    /// Package-relative paths with their contents, sorted by path.
    pub files: Vec<(&'static str, Cow<'static, [u8]>)>,
}

/// One family package that cletter's Typst sources import.
struct Family {
    namespace: &'static str,
    name: &'static str,
    version: &'static str,
    files: &'static [(&'static str, &'static [u8])],
}

/// The packages `typst/letter.typ` imports, at the versions Cargo resolved.
const FAMILY: [Family; 3] = [
    Family {
        namespace: cnice::typst::NAMESPACE,
        name: cnice::typst::NAME,
        version: cnice::typst::VERSION,
        files: cnice::typst::FILES,
    },
    Family {
        namespace: cdate::typst::NAMESPACE,
        name: cdate::typst::NAME,
        version: cdate::typst::VERSION,
        files: cdate::typst::FILES,
    },
    Family {
        namespace: cink::typst::NAMESPACE,
        name: cink::typst::NAME,
        version: cink::typst::VERSION,
        files: cink::typst::FILES,
    },
];

/// cletter's package followed by cnice, cdate and cink: everything a Typst
/// world needs to import [`spec`]. cletter's family imports are pinned to
/// the linked crate versions (see [Import versions](self#import-versions)).
///
/// With ctypst, for example:
///
/// ```ignore
/// let mut builder = ctypst::Engine::builder();
/// for package in cletter::typst::packages() {
///     builder = builder.package(&package.spec, package.files)?;
/// }
/// ```
#[must_use]
pub fn packages() -> Vec<Package> {
    let own = Package {
        spec: spec(),
        files: FILES
            .iter()
            .map(|&(path, bytes)| (path, pin_imports(bytes)))
            .collect(),
    };
    std::iter::once(own)
        .chain(FAMILY.iter().map(|family| {
            Package {
                spec: format!("@{}/{}:{}", family.namespace, family.name, family.version),
                files: family
                    .files
                    .iter()
                    .map(|&(path, bytes)| (path, Cow::Borrowed(bytes)))
                    .collect(),
            }
        }))
        .collect()
}

/// Replace the version of every `"@namespace/name:version"` family import
/// with the resolved crate version; other text stays untouched.
fn pin_imports(source: &'static [u8]) -> Cow<'static, [u8]> {
    let Ok(text) = std::str::from_utf8(source) else {
        return Cow::Borrowed(source);
    };
    let mut pinned = Cow::Borrowed(text);
    for family in &FAMILY {
        let prefix = format!("\"@{}/{}:", family.namespace, family.name);
        if !pinned.contains(&prefix) {
            continue;
        }
        let mut output = String::with_capacity(pinned.len());
        let mut rest: &str = &pinned;
        while let Some(start) = rest.find(&prefix) {
            let (before, after) = rest.split_at(start + prefix.len());
            output.push_str(before);
            let end = after.find('"').unwrap_or(after.len());
            output.push_str(family.version);
            rest = &after[end..];
        }
        output.push_str(rest);
        pinned = Cow::Owned(output);
    }
    match pinned {
        Cow::Borrowed(_) => Cow::Borrowed(source),
        Cow::Owned(text) => Cow::Owned(text.into_bytes()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;

    fn collect(root: &Path, dir: &Path, out: &mut Vec<(String, Vec<u8>)>) {
        for entry in std::fs::read_dir(dir).expect("readable directory") {
            let path = entry.expect("readable entry").path();
            if path.is_dir() {
                collect(root, &path, out);
            } else {
                let relative: Vec<String> = path
                    .strip_prefix(root)
                    .expect("path below the crate root")
                    .components()
                    .map(|part| part.as_os_str().to_str().expect("UTF-8 path").to_owned())
                    .collect();
                out.push((
                    relative.join("/"),
                    std::fs::read(&path).expect("readable file"),
                ));
            }
        }
    }

    /// Value of `key = "..."` in the `[package]` table of `typst.toml`.
    fn manifest_value(key: &str) -> String {
        let manifest = std::str::from_utf8(FILES[0].1).expect("typst.toml is UTF-8");
        let mut in_package = false;
        for line in manifest.lines().map(str::trim) {
            if line.starts_with('[') {
                in_package = line == "[package]";
            } else if in_package
                && let Some((name, value)) = line.split_once('=')
                && name.trim() == key
            {
                return value
                    .trim()
                    .strip_prefix('"')
                    .and_then(|rest| rest.strip_suffix('"'))
                    .expect("quoted string value")
                    .to_owned();
            }
        }
        panic!("typst.toml has no [package] {key}");
    }

    /// Every `"@namespace/name:version"` package import in `text`.
    fn imports(text: &str) -> Vec<String> {
        text.split('"')
            .skip(1)
            .step_by(2)
            .filter(|literal| literal.starts_with('@') && literal.contains(':'))
            .map(str::to_owned)
            .collect()
    }

    fn letter(package: &Package) -> String {
        let (_, bytes) = package
            .files
            .iter()
            .find(|(path, _)| *path == "typst/letter.typ")
            .expect("letter.typ is registered");
        String::from_utf8(bytes.to_vec()).expect("letter.typ is UTF-8")
    }

    fn family_specs() -> Vec<String> {
        vec![
            cnice::typst::spec(),
            cdate::typst::spec(),
            cink::typst::spec(),
        ]
    }

    #[test]
    fn files_match_disk() {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"));
        let mut disk = vec![(
            "typst.toml".to_owned(),
            std::fs::read(root.join("typst.toml")).expect("typst.toml exists"),
        )];
        collect(root, &root.join("typst"), &mut disk);
        disk.sort();
        let embedded: Vec<(String, Vec<u8>)> = FILES
            .iter()
            .map(|(path, bytes)| ((*path).to_owned(), bytes.to_vec()))
            .collect();
        let paths = |files: &[(String, Vec<u8>)]| -> Vec<String> {
            files.iter().map(|(path, _)| path.clone()).collect()
        };
        assert_eq!(
            paths(&embedded),
            paths(&disk),
            "FILES lists exactly the package files, sorted"
        );
        for ((path, embedded), (_, disk)) in embedded.iter().zip(&disk) {
            assert!(embedded == disk, "{path}: embedded bytes differ from disk");
        }
    }

    #[test]
    fn manifest_matches_crate() {
        assert_eq!(manifest_value("name"), NAME);
        assert_eq!(manifest_value("version"), VERSION);
        assert_eq!(NAME, env!("CARGO_PKG_NAME"));
        let entrypoint = manifest_value("entrypoint");
        assert!(
            FILES.iter().any(|(path, _)| *path == entrypoint),
            "entrypoint {entrypoint:?} is embedded"
        );
        assert_eq!(
            spec(),
            format!("@preview/cletter:{}", env!("CARGO_PKG_VERSION"))
        );
    }

    #[test]
    fn packages_are_cletter_then_its_family() {
        let packages = packages();
        let specs: Vec<String> = packages
            .iter()
            .map(|package| package.spec.clone())
            .collect();
        let mut expected = vec![spec()];
        expected.extend(family_specs());
        assert_eq!(specs, expected);
        let family = [cnice::typst::FILES, cdate::typst::FILES, cink::typst::FILES];
        for (package, files) in packages[1..].iter().zip(family) {
            let registered: Vec<(&str, &[u8])> = package
                .files
                .iter()
                .map(|(path, bytes)| (*path, bytes.as_ref()))
                .collect();
            assert_eq!(registered, files, "{} is its crate's package", package.spec);
        }
        let paths: Vec<&str> = packages[0].files.iter().map(|(path, _)| *path).collect();
        let disk: Vec<&str> = FILES.iter().map(|(path, _)| *path).collect();
        assert_eq!(paths, disk);
    }

    #[test]
    fn family_imports_name_exactly_the_registered_packages() {
        let source = std::str::from_utf8(FILES[3].1).expect("letter.typ is UTF-8");
        assert_eq!(FILES[3].0, "typst/letter.typ");
        let registered = imports(&letter(&packages()[0]));
        let mut seen = registered.clone();
        seen.sort();
        seen.dedup();
        let mut expected = family_specs();
        expected.sort();
        assert_eq!(seen, expected, "letter.typ imports each family package");
        assert_eq!(
            registered.len(),
            imports(source).len(),
            "pinning keeps every import"
        );
        // Only the import versions change.
        let strip = |text: &str| -> String {
            let mut text = text.to_owned();
            for literal in imports(&text) {
                let name = literal.split(':').next().unwrap().to_owned();
                text = text.replace(&format!("\"{literal}\""), &format!("\"{name}\""));
            }
            text
        };
        assert_eq!(strip(&letter(&packages()[0])), strip(source));
    }

    #[test]
    fn source_imports_are_compatible_with_the_resolved_crates() {
        let source = std::str::from_utf8(FILES[3].1).expect("letter.typ is UTF-8");
        let numbers = |version: &str| -> Vec<u64> {
            version
                .split('.')
                .map(|part| part.parse().expect("numeric version"))
                .collect()
        };
        for literal in imports(source) {
            let (name, version) = literal.split_once(':').unwrap();
            let family = FAMILY
                .iter()
                .find(|family| format!("@{}/{}", family.namespace, family.name) == name)
                .unwrap_or_else(|| panic!("{literal} is not a family package"));
            let (required, resolved) = (numbers(version), numbers(family.version));
            assert_eq!(
                required[..2],
                resolved[..2],
                "{literal} and the linked {} {} share a 0.x release line",
                family.name,
                family.version
            );
            assert!(
                required <= resolved,
                "{literal} is not newer than the crate"
            );
        }
    }

    #[test]
    fn pinning_replaces_any_import_version_and_nothing_else() {
        let source: &'static [u8] =
            b"#import \"@preview/cnice:0.0.1\": greet\n#import \"@preview/cdate:9.9.9\" as d\n\
              #let note = \"@preview/cnicer:0.0.1 stays\"\n";
        let pinned = String::from_utf8(pin_imports(source).into_owned()).unwrap();
        assert_eq!(
            pinned,
            format!(
                "#import \"{}\": greet\n#import \"{}\" as d\n\
                 #let note = \"@preview/cnicer:0.0.1 stays\"\n",
                cnice::typst::spec(),
                cdate::typst::spec()
            )
        );
        let untouched: &'static [u8] = b"#let plain = 1\n";
        assert!(matches!(pin_imports(untouched), Cow::Borrowed(_)));
    }
}
