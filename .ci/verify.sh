#!/usr/bin/env bash
set -euo pipefail
exec 2>&1
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
export CARGO_TERM_COLOR="${CARGO_TERM_COLOR:-always}"
export RUST_TEST_THREADS="${RUST_TEST_THREADS:-2}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-stable}"
export UV_PYTHON="${UV_PYTHON:-python3}"
export UV_PYTHON_DOWNLOADS="${UV_PYTHON_DOWNLOADS:-never}"
: "${CI_COMMIT_SHA:?verify requires the exact source revision}"
: "${ARTIFACT_ROOT:?verify requires an absolute ARTIFACT_ROOT}"
[[ "$ARTIFACT_ROOT" = /* ]] || { echo "ARTIFACT_ROOT must be absolute" >&2; exit 2; }
# Hosted route mirror: .github/workflows/ci.yml case branches (rust/fmt/release-config)
# plus every ccid-defined standalone packaging/integration selector in dependency order
# (js-package before js-pnpm/js-yarn/js-bun; packaging before registry reads).
# Excluded by hosted policy, kept callable: release, rust-dependencies, typst-preview
# (this repo also: typst-conformance, resolve-dependencies).
python3 .ci/check.py metadata
cargo fmt --all -- --check
cargo test --locked
cargo clippy --all-targets --locked -- -D warnings
python3 .ci/check.py javascript
python3 .ci/check.py js-package
python3 .ci/check.py js-pnpm
python3 .ci/check.py js-yarn
python3 .ci/check.py js-bun
python3 .ci/check.py python-package
python3 .ci/check.py typst-package
python3 .ci/check.py typst-conformance
python3 .ci/check.py rust-package
python3 .ci/release-check.py
