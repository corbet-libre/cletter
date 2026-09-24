# Changelog

All notable changes to `cletter` are documented here. The project follows
Semantic Versioning.

## 0.4.1 - 2026-09-25

- Repository moved to github.com/corbet-foss/cletter; registry metadata points there.
- Released from a single tag through CI (crates.io and JSR trusted publishing).
- Drop the duplicate `LICENSES/LGPL-3.0-only WITH LGPL-3.0-linking-exception.txt`
  (identical to `LGPL-3.0-linking-exception.txt`); JSR rejects paths with spaces.
- Require the sibling releases without that file: cnice 0.1.2, cdate 0.3.2 and
  cink 0.2.1 (npm pins them exactly, as JSR import rewriting requires);
  resolve cnice from crates.io, not a local checkout.

## 0.4.0 - 2026-09-18

- Compose `cnice` (new `greet` + `farewell` facade, superseding `cgreet` and
  `cfarewell`) instead of depending on those two crates directly. The
  re-exported salutation/closing API is unchanged; all 108 conformance
  vectors still pass in Rust, JavaScript, Python and Typst.
- Fix Python dependency bounds to the current lines
  (`cnice>=0.1,<0.2`, `cdate>=0.3,<0.4`, `cink>=0.2,<0.3`).
- Vendor `cnice` Typst sources (with content hashes) instead of the
  `cgreet`/`cfarewell` snapshots.
- Route every covered locale through the uniform salutation renderer (no
  per-language branch; coverage is table data): `Region`, `parse_region`,
  `region_uses_comma`, `de_salutation` and `de_honorific_warning` are gone,
  replaced by locale-keyed `salutation_*` parsers, `honorific_warning` and
  `is_supported` (re-exported as `salutation_supported`). Named openings
  with an explicit honorific now render fully ("Sehr geehrte Frau Dr.
  Müller" instead of "Sehr geehrte/r Frau Dr. Müller"); names without one
  fall back to the formal template (never invented familiarity). French,
  Italian, Romansh and English render through the same matcher.

## 0.3.0 - 2026-09-13

- License this new release line under LGPL-3.0-only WITH LGPL-3.0-linking-exception across Cargo, npm, JSR,
  Python and Typst, with the complete LGPL and incorporated GPL notices.
- Keep runtime behavior, correspondence tables and dependency versions unchanged.

## 0.2.2 - 2026-09-11

- Add explicit locale-ID spelling normalization in Rust, JavaScript, Python and
  Typst without dropping subtags, inferring regions or applying table fallbacks.
- Keep supported-language resolution behavior and correspondence tables unchanged.

## 0.2.1 - 2026-09-11

- Refresh the self-contained Typst family.
- Preserve existing runtime behavior, APIs and shared tables.

## 0.2.0 - 2026-09-09

- Reuse packed distributions and run selected checks through Crow.
- **Breaking:** returned locale IDs are lowercase; mixed-case inputs remain accepted. Add Liechtenstein German (`de-li`).
- Resolve overlapping country keywords deterministically in canonical table order.
- Share explicit sharp-S diagnostics and conversion across Rust, JavaScript, Python and Typst.

- Ship compiled ESM and CommonJS, declaration files, and a standalone browser module.
- Add a Python distribution with shared-vector conformance and a JSON CLI.
- Add JSR packaging, installed-artifact tests, and complete registry license files.
- Clarify scope, examples, installation options, and family links on the product page.
- Resolve locale codes case-insensitively, preserving regional defaults.
- Re-export the cdate calendar-formatting functions.

## 0.1.1 - 2026-09-06

- Republish: npm held 0.1.0 invisible on reads while blocking overwrite
  on writes, so the release moved forward. No code change.

## 0.1.0 - 2026-09-06

- Initial release: locale resolution (language + location to BCP 47),
  openings (formal/named templates, 30 locales), subjects
  (prefix + title / unsolicited), Swiss orthography, region mapping into
  `cgreet`, and aggregated advisories — composing `cgreet`, `cfarewell`
  and `cink` as a Rust crate, a pure-TypeScript package, and a Typst
  module sharing one table set and one vector suite.
