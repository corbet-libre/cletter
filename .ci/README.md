# Focused validation and release preparation

Crow runs `.ci/ccid.toml` through the pinned native `ccid` command library.
The repository commands also work on a suitably provisioned build host.
Workstations stage committed source and inspect evidence; they do not compile it.
GitHub Actions has an equivalent manual public-source check route; publication
remains a separate operation.

## Manual GitHub Actions route

When hosted execution is available, free, and appropriate for the public inputs,
run `.github/workflows/ci.yml` with a comma-separated `checks` selection. It uses
the same repository commands on Linux with two Cargo build/test threads and a
15-minute job limit. Default selection: `metadata,rust`. Rust selects current
`stable`; the optional `rust-msrv` check reads the minimum from `Cargo.toml` and
runs separately. It does not fix the default compiler to that minimum.

JavaScript, package, and published-consumer selectors provision only their needed
hosted tools. For additional manager coverage, select `js-package` before
`js-pnpm`, `js-yarn`, or `js-bun` in the same run. The resulting artifact contains
package receipts plus `hosted-run.json`, with the source/archive/workflow identity,
locked input hashes, actual tools, and final check outcome. Hosted evidence does
not claim execution by ccid or native Windows/macOS coverage.

Checks requiring operator-supplied artifact manifests (`rust-dependencies` and,
where defined, `typst-preview`) stay on Crow. Private inputs and publishing
credentials never enter this hosted workflow. Public registry consumer checks
fail visibly when their exact dependency versions have not been published.

This manual workflow is not an expanded automatic provider mapping. Keep any
existing `.ci/providers.toml` pilot unchanged until equivalent hosted execution
and fallback identity are proved. Confirm unavailable execution before falling
back to Crow; a failed test is not provider unavailability. Publication remains
separate from these credential-free preparation/check jobs.

## Publishing prepared artifacts

The checked-in `.ci/publish.py` adapter uses the exact shared publisher resource
from the release workflow's verified ccid archive. It imports existing source
archives, preparation receipts and tested packages into one reviewed bundle;
producer identities remain distinct from later CI/publisher commits. See the
[shared import and publication contract](https://github.com/corbet-infra/ccid/blob/main/adapters/registry-publish.md).

The manual Crow `release` workflow reconciles existing bytes by default. Supply
`RELEASE_BUNDLE` (an existing worker file), `RELEASE_BUNDLE_SHA256`, and optionally
`RELEASE_CHANNELS`; select exactly one registry with `RELEASE_OPERATION=publish`
for an intended upload. `publish` with `all` is refused; status can inspect all.
Bundle inspection has no credentials. Registry status loads only the GitHub
release token; publication loads that token and the selected registry
token in its own guarded step. Missing tokens for other registries do
not block inspection, status or a selected upload. Python publication requires
`PYPI_TOKEN`; its absence is an explicit missing prerequisite, not a skipped
success. No build occurs with these credentials.

The manual GHA `release.yml` workflow consumes the same exact bundle from a public
release asset. It can reconcile all public channels and publish Cargo through
configured short-lived OIDC. Token-backed npm, JSR and PyPI publication stays on
Crow. The existing release/tag is verified before uploads. Persistent local and
immutable GitHub release journals prevent retries after an ambiguous upload,
including across providers; no registry restriction is automatically changed.

These adapters do not expand automatic provider mappings, create release tags,
or establish hosted/native execution proof. Existing check recipes and the
release publisher have separate explicit tool pins. Select `release-config` to
check adapter identities, Python/shell syntax and manual credential boundaries
without compiling products or accessing registries. Actionlint is required: Crow
uses the existing tool on PATH or in the Nix store; hosted setup provisions it
only for this selector. Evidence records its actual path and version. The
repository checker installs nothing and fails if the required tool is absent.

Select checks from changed inputs and missing evidence. A changed README does not
require another Rust build. Table/API changes need affected language vectors;
package metadata, exports and dependency changes need installed-package checks.
Use a broader selection when the impact is unknown. Existing results are reusable
only for matching source, dependency closure, tools, configuration and environment.

| Selector | Coverage |
| --- | --- |
| `metadata` | Version alignment and byte-for-byte generated assets |
| `release-config` | Manual release adapter contract and Python/shell syntax; required provisioned Actionlint |
| `fmt` | Rust formatting only |
| `rust` | Locked Rust tests including doctests, formatting, Clippy with denied warnings |
| `rust-msrv` | Minimum Rust tests; Crow requires provisioned 1.94.0, while hosted setup reads `Cargo.toml` |
| `javascript` | Strict TypeScript and shared source vectors |
| `rust-package` | Build and verify the registry-resolved Cargo package |
| `js-package` | Pack once; installed npm/Node/Bun imports and declarations, browser module, JSR dry-run |
| `js-pnpm`, `js-yarn`, `js-bun` | Selected additional manager consuming the same verified npm tarball |
| `python-package` | Wheel/sdist, installed-wheel vectors, metadata and JSON CLI consumers |
| `typst-package` | Deterministic archive and actual installed Typst import |
| `typst-conformance` | All shared vectors against the Typst source, using an existing compiler or cached Python Typst module offline |
| `rust-dependencies` | Pre-publication source tests using checksum-verified sibling crates in private scratch |
| `resolve-dependencies` | Resolve published sibling Cargo/npm versions in scratch and export both lockfiles for review |
| `published-npm`, `published-jsr`, `published-python` | Consumers of the exact version on the selected live registry |

For example, use the existing dispatcher:

```sh
crow-ci plan --repo . --workflow ccid --var CHECKS=metadata,rust
crow-ci run --repo . --workflow ccid --var CHECKS=metadata,rust
```

Before an initial release, choose all affected source and distribution checks:

```sh
crow-ci run --repo . --workflow ccid \
  --var CHECKS=metadata,rust,javascript,rust-package,js-package,python-package,typst-package \
  --var ARTIFACT_ROOT=/absolute/persistent/release-artifacts
```

`ARTIFACT_ROOT` is a worker path supplied by the operator. Each package selector
exports immutable files under `<root>/<package>/<commit>/`, plus its own JSON
receipt, `SOURCE_COMMIT`, and an aggregate `SHA256SUMS`. Additional manager checks
require `js-package` evidence for that exact commit. They never rebuild the tarball.
Use them when manager/export/packaging behavior changed; do not repeat all managers
for every source edit. Publication uploads the verified files separately using
registry credentials outside these verification jobs.

For unpublished sibling dependencies, supply `DEPENDENCY_MANIFEST` and
`DEPENDENCY_MANIFEST_SHA256`. The manifest is an exact JSON document:

```json
{
  "schema": 1,
  "artifacts": [
    {
      "kind": "wheel",
      "name": "cgreet",
      "path": "/absolute/path/to/verified/cgreet.whl",
      "sha256": "the actual 64-character lowercase SHA-256"
    }
  ]
}
```

Kinds are `wheel`, `crate`, or `npm`; each consuming check selects its own kind.
Python installs the specified sibling wheels alongside its own wheel. The
`rust-dependencies` selector copies source and verified sibling crates to owned
scratch, uses temporary Cargo patches and a scratch-only lock, and runs the tests.
This is integration evidence, not registry package verification. `rust-package`
always uses normal registry resolution and requires published dependencies.
Neither the source tree nor the released manifest acquires local path patches.

After the four sibling versions declared in `Cargo.toml` and the JavaScript
`package.json` are published on crates.io and npm, prepare cletter's registry locks:

```sh
crow-ci run --repo . --workflow ccid \
  --var CHECKS=resolve-dependencies \
  --var ARTIFACT_ROOT=/absolute/persistent/release-artifacts
```

This selector runs targeted `cargo update -p cgreet -p cfarewell -p cdate -p cink`
and `bun install --lockfile-only --ignore-scripts` in a copied source tree. It
requires the exact declared sibling crate versions and registry checksums; it
does not use local dependency patches or build packages. The exported `Cargo.lock`
and `bun.lock` have hashes in `resolve-dependencies.json` and `SHA256SUMS`. Verify
the receipt against the dispatched commit, review and copy those two files into
their repository locations, then commit before running final installed-package
validation. Resolving a lockfile is preparation, not passing build/test evidence.

The shared runner bounds concurrency to two build/test threads by default and
selected checks to 900 seconds; `CI_JOBS`, `CI_TEST_THREADS`, and `CI_TIMEOUT` can
supply a concrete different budget. It inherits dedicated package caches and
namespaces Cargo targets by canonical repository identity. It verifies source and
tool digests, preserves unchanged source freshness, supervises timeout/cancellation,
and never clears caches or installs system tools. Commands that generate source or
install dependencies run in owned scratch copies, preserving the verified input
tree and its reusable Rust timestamps. The dispatcher checks host
headroom, attaches to identical active work, and refuses a repeated completed
request unless an operator explicitly requests a diagnosed rerun.

Inspect existing runs before dispatch. After a failed Python check, select Python
again after correcting its inputs; a passed unrelated Rust check remains evidence.
Keep exact check receipts and durations when assessing whether wider validation is
needed. Linux results do not establish native Windows/macOS behavior or another
Rust/Node/Python version. Unavailable checks remain explicitly unverified.

Select `typst-conformance` for Typst implementation, shared-vector or serializer
changes; the installed-package smoke test alone does not run the full corpus.
Its Python fallback reuses the existing `typst==0.15.0` cache with networking and
Python downloads disabled, and fails if that compiler is unavailable. The vector
script itself never installs a compiler. Its receipt records the exact checked
source commit; reuse against an earlier package release requires verifying that
the Typst implementation and shared vectors are unchanged.

`typst-family-preview` checks SHA-bound prepared Universe archives for all four
Apache family packages and compiles every README preview-import example. Supply
the four `typst-preview` entries through the existing dependency manifest.
