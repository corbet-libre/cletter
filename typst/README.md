# Typst correspondence facade

`letter.typ` is the entrypoint of the `@preview/cletter` package. It contains
the generated locale tables and imports the family packages `@preview/cnice`,
`@preview/cdate` and `@preview/cink` at the exact versions `Cargo.toml`
requires; install those beside cletter (see the installation guide). No family
source is copied into this directory.

```typst
#import "letter.typ": salutation, closing, long-date, orthography-issues
#salutation("de-li", "Frau Dr. Müller")
#closing("de-li")
#long-date("de-li", 2026, 9, 9)
#assert.eq(orthography-issues("de-li", "Grüße"), (("ß", "ss"),))
```

The facade reexports cnice's salutation and recipient-advisory helpers
(`greet`) and closing (`farewell`), cdate's date formats, and cink's
`signature-image`.
Opening, subject, locale resolution and orthography remain cletter-owned.
Locale IDs are lowercase; mixed-case inputs resolve compatibly. Explicit
opening/subject/closing overrides and recipient names are preserved verbatim.

`normalize-locale-id(" EN_CH ")` returns `"en-ch"` without inferring a region
or falling back through the correspondence tables. It preserves all explicit
subtags. It trims only ASCII space, tab, LF, CR, VT and FF, replaces underscores
with hyphens and lowercases ASCII letters. Other characters, including U+FEFF
and U+0085, remain for caller validation. Callers validate syntax and their
supported locale shape separately.
`normalize-language` and `resolve-locale` retain their supported-table behavior.

`apply-ortho` performs literal substitutions only on caller-selected prose.
`orthography-issues` reports applicable pairs without changing text. The caller
excludes names, quotations, URLs and exact source material; neither helper
infers protected boundaries or evaluates a letter's evidence, tone or argument.

Rust hosts that embed Typst register everything with
`cletter::typst::packages()`: cletter plus the cnice, cdate and cink packages
embedded in their own crates. It pins the family imports to the crate versions
Cargo resolved, so a newer compatible family release needs no edit here.

Change family behavior in its owning library. To run the conformance vectors
against sibling checkouts, from the cletter checkout:

```sh
python3 scripts/typst-conformance.py /path/to/family-checkouts
```

The driver stages each checkout as its offline `@preview` package, uses an
existing `typst` or `tinymist` compiler or the Python `typst` module, and runs
all canonical JSON vectors for cnice, cdate and cletter. The cink Typst helper
renders a sized image; decoding and sizing vectors belong to its Rust,
TypeScript and Python ports.
