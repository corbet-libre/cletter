# Installation and distribution

The main branch ships 0.4.0 under LGPL-3.0-only WITH LGPL-3.0-linking-exception, published to registries. The existing releases documented below keep their original
license grants; this change does not replace their artifacts.

The JavaScript, Rust and Typst examples below describe version 0.4.0;
Python installation uses the published 0.4.0 release. Check the linked registry
or release for availability; a source manifest alone does not establish publication.

## JavaScript and Rust

Use Cargo for Rust and npm, pnpm, Yarn, or Bun for JavaScript. These JavaScript
package managers share the npm registry; each consumes the same package.
Deno can use `npm:@corbet-foss/cletter`. The browser export bundles runtime
dependencies and needs no import map. The declared Rust minimum is 1.94. Release checks use the worker's current stable compiler; a separate minimum-version check is required to
verify that lower bound.

## Python and the command line

The pure Python package requires Python 3.10+ and is published on
[PyPI](https://pypi.org/project/cletter/0.4.0/). Version 0.2.1 retains
[Apache-2.0](https://github.com/corbet-labs/cletter/blob/v0.2.1/LICENSE);
the LGPL-3.0-only WITH LGPL-3.0-linking-exception terms on main apply to the 0.4.0 release line.
Install the PyPI release with pip or uv in your Python environment:

```sh
python -m pip install cletter==0.4.0
```

```sh
uv pip install cletter==0.4.0
```

For a uv project, `uv add cletter==0.4.0` adds the package to your dependencies.
The installer retrieves cnice,
cdate and cink from PyPI automatically.

After installation, functions can be called from Python or through either CLI
entrypoint:

```sh
cletter --help
python -m cletter --help
```

The CLI takes a function name and a JSON array of positional arguments or an
object of keyword arguments. Use `-` to read arguments from stdin. It writes
JSON to stdout; errors use stderr and a nonzero exit status. Image bytes in
the `normalize` result are base64 strings.

For an isolated CLI environment, use `pipx install cletter==0.4.0` or
`uv tool install cletter==0.4.0`.

The wheel contains no native extensions and is platform independent. Release
evidence records the Python version and operating system actually exercised.
Verified wheels and source distributions are also attached to the
[GitHub release](https://github.com/corbet-foss/cletter/releases/tag/v0.4.0).
The Python 0.2.1 API predates `normalize_locale_id`, which appears in newer
source documentation.

## JSR

The JSR distribution is named
[`@corbet-foss/cletter`](https://jsr.io/@corbet-foss/cletter@0.4.0):

```sh
deno add jsr:@corbet-foss/cletter@0.4.0
```

The JSR facade imports its published npm components. In an existing Node project,
install the declared dependencies with `deno install`, or let Deno resolve them
for a standalone call with `deno run --node-modules-dir=auto app.ts`.

## Typst

Download `cletter-0.4.0-typst.tar.gz` from the matching GitHub release and
extract its contents into `typst/packages/local/cletter/0.4.0` under your
[Typst data directory](https://github.com/typst/packages#local-packages):

| System | Data directory |
| --- | --- |
| Linux | `$XDG_DATA_HOME`, or `~/.local/share` |
| macOS | `~/Library/Application Support` |
| Windows | `%APPDATA%` |

```typst
#import "@local/cletter:0.4.0": *
```

The archive includes its manifest, tables, source, and licenses. CI compiles
an example against a fresh installation of the actual archive with Typst 0.15.
For the Typst web app, upload the extracted files and import the entrypoint
listed in `typst.toml` by its relative path.

For signature images, load bytes in your document so paths resolve from the
document directory:

```typst
#signature-image(read("signature.svg", encoding: none), 24)
```

The Typst image helper places an image. Header parsing, pixel limits, and
sizing calculations are available in the Rust, JavaScript, and Python APIs.

The Apache-2.0 release is submitted to Typst Universe in
[PR #5820](https://github.com/typst/packages/pull/5820), alongside the other
correspondence components. The prepared preview examples passed on Typst 0.15.0.
The listing awaits review and publication; use the local archive above until
the preview package is available.

## System package managers

These are language libraries, with a portable Python CLI. Homebrew, APT, RPM,
WinGet, Chocolatey, and Scoop are not additional registries for importing a
Rust crate or JavaScript module. Use their Python or Node runtime and the
language package manager above. No native system-package listing is claimed.
