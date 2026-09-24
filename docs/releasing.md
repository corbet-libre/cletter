# Releasing cletter

Keep Cargo.toml, Cargo.lock, package.json, jsr.json, pyproject.toml, and
typst.toml versions consistent. Published contents are immutable: use a new
version for corrections.

1. Update versions and CHANGELOG.md (a `## X.Y.Z - date` section becomes the
   release notes), then regenerate canonical tables with
   `bash js/@corbet-labs/cletter/scripts/sync-assets.sh`. After updating the
   sibling versions, run `python scripts/sync-typst-family.py /path/to/family`
   against their final checkouts and review both versions and hashes in
   `typst/vendor/manifest.json`. Commit to `main`.
2. Optionally rehearse: run `.github/workflows/release.yml` from `main` without
   a tag (`gh workflow run release.yml --ref main`). It runs the release checks
   and imports and inspects the bundle, retaining it as a workflow artifact.
   It creates no release and publishes nothing.
3. Push the tag `vX.Y.Z` for the version in `Cargo.toml`. The tag push is the
   only release trigger; `release.yml` then runs three jobs:
   - `prepare` (read-only, no credentials) calls `ci.yml` at the tag with
     `metadata,release-config,rust,javascript,rust-package,js-package,python-package,typst-package`.
     Each package is built once and exported with its receipt and `hosted-run.json`.
   - `bundle` (`contents: write`) requires tag == `v` + version, recreates the
     exact source archive, imports those packages for Cargo, npm, JSR and PyPI
     with `.ci/publish.py bundle` (the [shared import contract](https://github.com/corbet-libs/ccid/blob/27c248aefa3c7198be6716a884d290c717774b21/adapters/registry-publish.md)),
     inspects it offline, and creates the GitHub release with
     `publication-bundle.tar`, its `.sha256` and the import receipt `publication-bundle.json`.
   - `publish` (`contents: write`, `id-token: write`) downloads that release
     bundle, runs `status`, and uploads only missing packages: Cargo through
     `rust-lang/crates-io-auth-action`, JSR through GitHub OIDC
     (`RELEASE_JSR_AUTH=trusted`). npm and PyPI have no trusted publisher
     rules yet; the job reports them as deferred without failing.
4. Upload deferred npm and PyPI packages from the same release bundle with
   registry tokens (below). The publisher verifies the live tag and release,
   journals each upload on the release, and verifies the public bytes.
5. Run the published-consumer checks (`published-npm`, `published-jsr`,
   `published-python`) and state the status per registry. A successful upload
   response or version collision is insufficient proof.

Publish sibling dependencies before cletter and resolve its committed locks
against those registry versions. Local path overrides are integration evidence.

## Re-running

A transient failure is retried with "Re-run failed jobs"; earlier jobs'
packages are reused. To reconcile or publish an existing release again (for
example after a registry rule is added), dispatch `release.yml` with
`tag=vX.Y.Z`: it skips `prepare` and `bundle` and publishes from the release's
existing bundle. Uploads are never repeated after an uncertain outcome; the
release journals block them. If `bundle` fails before the release exists and
nothing was published, fix `main`, then delete and re-push the tag or release a
new patch version.

## Operator upload for npm and PyPI

Until npm and PyPI trust `corbet-foss/cletter:release.yml`, upload them from the
release bundle on a workstation. No build runs; the publisher only verifies and
uploads the reviewed bytes. It needs `GH_TOKEN` with `contents: write` on this
repository (for the publication journals), and `NPM_TOKEN` or `PYPI_TOKEN` for
the selected registry:

```sh
tag=vX.Y.Z repo=corbet-foss/cletter rev=27c248aefa3c7198be6716a884d290c717774b21
work=$(mktemp -d) && cd "$work"
git clone -q --depth 1 --branch "$tag" "https://github.com/$repo" source
git clone -q https://github.com/corbet-libs/ccid publisher && git -C publisher checkout -q "$rev"
git -C publisher archive --format=tar HEAD > publisher.tar
gh release download "$tag" -R "$repo" -p publication-bundle.tar -p publication-bundle.tar.sha256
sha256sum --check --strict publication-bundle.tar.sha256
export CCID_REVISION="$rev" CI_TOOL_ARCHIVE="$PWD/publisher.tar" \
  CI_TOOL_SHA256="$(sha256sum publisher.tar | cut -d ' ' -f 1)" \
  RELEASE_BUNDLE="$PWD/publication-bundle.tar" \
  RELEASE_BUNDLE_SHA256="$(cut -d ' ' -f 1 publication-bundle.tar.sha256)" \
  RELEASE_JOURNAL_ROOT="$PWD/journals" GH_TOKEN="$(gh auth token)"
python3 source/.ci/publish.py status
NPM_TOKEN="$(sops --decrypt ~/agents/knowledge/secrets/npm.yml | yq -r .api_token)" \
  python3 source/.ci/publish.py publish --channels npm
PYPI_TOKEN="$(sops --decrypt ~/agents/knowledge/secrets/pypi.yml | yq -r .api_token)" \
  python3 source/.ci/publish.py publish --channels pypi
```

`rev` is the `CCID_REVISION` pinned in the tag's `release.yml`. Keep the
`journals` directory until every registry reports its package as verified.

Crow keeps a manual `release` route for the same bundle if GitHub Actions is
unavailable. Credentials remain outside repository source and check jobs.
Registry account controls are read as prerequisites; these adapters never
change registry policy or create trusted publisher rules.

The npm registry serves npm, pnpm, Yarn, Bun, Deno's npm imports, and browser
CDNs. A successful Linux check does not prove native Windows/macOS behavior.
Minimum-runtime checks are separate from current-runtime checks. Record any
unavailable runtime or registry explicitly instead of marking it verified.

The Typst archive installs into an `@local` package namespace. Typst Universe
requires a separate eligible submission; see [installation](installation.md).
The release run's `prepare` artifact retains the checked Typst archive and receipt
for 14 days.
