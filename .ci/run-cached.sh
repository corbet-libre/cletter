#!/usr/bin/env bash
# Execute the manifest's selected checks with content-keyed result reuse.
set -euo pipefail
exec 2>&1
: "${CCID_BIN:?Missing verified ccid job runtime}"
: "${CI_COMMIT_SHA:?Missing verified source revision}"
: "${CI_REPOSITORY_URL:?Missing canonical repository identity}"
: "${CHECKS:?Missing declared check selection}"
if [ "$CHECKS" != "verify,published-npm,published-jsr,published-python,resolve-dependencies" ]; then
  echo "CHECKS must be exactly 'verify,published-npm,published-jsr,published-python,resolve-dependencies', got: $CHECKS" >&2
  exit 2
fi
test -f Cargo.lock || { echo 'Cargo.lock must be present (committed snapshot)' >&2; exit 2; }
cache_root=${CI_CACHE_ROOT:-${CARGO_HOME:-}}
[[ $cache_root = /* ]] || { echo 'An absolute persistent CI_CACHE_ROOT or CARGO_HOME is required' >&2; exit 2; }
namespace=$(printf '%s' "$CI_REPOSITORY_URL" | sha256sum | cut -c1-24)
state="$cache_root/ccid-cached/$namespace"
toolchains=${CI_TOOLCHAIN_ROOT:-$cache_root/ccid-cached/toolchains}
[[ $toolchains = /* ]] || { echo 'CI_TOOLCHAIN_ROOT must be absolute' >&2; exit 2; }
mkdir -p "$state" "$toolchains"
exec 9>"$state/lock"
flock -w "${CI_TIMEOUT:-2700}" 9
mkdir -p "$state/moon-cache/hashes" "$state/moon-cache/outputs" "$state/moon-home"
mkdir -p .moon/cache
ln -sfn "$state/moon-cache/hashes" .moon/cache/hashes
ln -sfn "$state/moon-cache/outputs" .moon/cache/outputs
# Binding gates: node+npm serve check.py js-package/managers (npx fetches pinned pnpm@10/yarn@1
# per-run; bun.lock stays frozen); bun serves install/typecheck/conformance; deno serves
# js-package dry-run/published-jsr; uv+python3 serve hatchling wheel/sdist + typst==0.15.0 packaging.
tool_source=github:NixOS/nixpkgs/b7c2ada94fe99c15b0dbcf4d11fd7850b957a436
tool_paths=$(nix build --no-link --print-out-paths "$tool_source#moon" "$tool_source#proto" "$tool_source#nodejs_24" "$tool_source#bun" "$tool_source#deno" "$tool_source#uv" "$tool_source#python3")
for path in $tool_paths; do PATH="$path/bin:$PATH"; done
export PROTO_HOME="$toolchains/proto" RUSTUP_HOME="$toolchains/rustup"
shared_cargo_home=${CARGO_HOME:-}
export CARGO_HOME="$toolchains/cargo" MOON_HOME="$state/moon-home"
export PROTO_AUTO_CLEAN=false PROTO_TELEMETRY=false PROTO_YES=true
export RUSTUP_INIT_SKIP_PATH_CHECK=yes RUSTUP_TOOLCHAIN=stable
export PATH="$(dirname "$CCID_BIN"):$CARGO_HOME/bin:$PROTO_HOME/shims:$PROTO_HOME/bin:$PATH"
export CI_JOBS="${CI_JOBS:-2}" CARGO_BUILD_JOBS="${CI_JOBS:-2}"
export RUST_TEST_THREADS="${CI_TEST_THREADS:-2}"
export UV_PYTHON=python3 UV_PYTHON_DOWNLOADS=never
export CARGO_NET_GIT_FETCH_WITH_CLI=true
if [ -n "${GIT_CONFIG_COUNT:-}" ]; then
  echo 'GIT_CONFIG_COUNT is already set; refusing to overwrite job git config' >&2
  exit 2
fi
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0='url.https://git.corbet.ch/corbet-libs/.insteadOf'
export GIT_CONFIG_VALUE_0='https://github.com/corbet-libs/'
export GIT_CONFIG_KEY_1='url.https://git.corbet.ch/corbet-foss/.insteadOf'
export GIT_CONFIG_VALUE_1='https://github.com/corbet-foss/'
# Shared-first toolchain lock: jobs share a provisioned toolchain and take
# exclusive only to provision missing pieces. Same lock file, so old
# whole-job-exclusive runners interoperate (they just serialize).
TOOLCHAIN_LOCK_FILE="$toolchains/install.lock"
TOOLCHAIN_LOCK_TIMEOUT="${CI_TIMEOUT:-2700}"
TOOLCHAIN_WANT_NIGHTLY=0
TOOLCHAIN_WASM_TARGETS=""
# shellcheck source=toolchain-lock.sh
source "$(dirname "${BASH_SOURCE[0]}")/toolchain-lock.sh"
# MSRV comes from the SAME gate->main flow: TOOLCHAIN_EXTRA_TOOLCHAINS is
# readiness-probed under shared and installed under exclusive inside
# toolchain_ensure (repo-local helper extension; production helper untouched).
# Derive + pin here so drift fail-closes before provisioning.
MINIMUM_RUST="$(python3 -c 'import re,tomllib;v=tomllib.load(open("Cargo.toml","rb"))["package"]["rust-version"];v=v if v.count(".")==2 else v+".0";print(v)')"
test "$MINIMUM_RUST" = "1.94.0" || { echo "Cargo rust-version drifted: $MINIMUM_RUST" >&2; exit 2; }
TOOLCHAIN_EXTRA_TOOLCHAINS="$MINIMUM_RUST"
toolchain_ensure
# Per-repo helper installs: no cargo-installed helpers exist in these gates (maturin/typst
# arrive via uv, pnpm/yarn via npx, wasm via cargo run from source); keep a per-repo
# install root on PATH so any future helper never mutates shared CARGO_HOME.
export CARGO_INSTALL_ROOT="$state/install-bin"
mkdir -p "$CARGO_INSTALL_ROOT/bin"
export PATH="$CARGO_INSTALL_ROOT/bin:$PATH"
cargo_bin=$("$CARGO_HOME/bin/rustup" which --toolchain stable cargo)
test -x "$cargo_bin"
export PATH="$(dirname "$cargo_bin"):$PATH"
# Receipt parity with hosted CI: absolute ARTIFACT_ROOT plus source digest (read-only git).
export ARTIFACT_ROOT="${ARTIFACT_ROOT:-$state/release-artifacts}"
mkdir -p "$ARTIFACT_ROOT"
[[ "$ARTIFACT_ROOT" = /* ]] || { echo "ARTIFACT_ROOT must be absolute" >&2; exit 2; }
export SOURCE_SHA256="$(git archive --format=tar HEAD | sha256sum | cut -d ' ' -f 1)"
export CCID_SOURCE_REVISION="$CI_COMMIT_SHA"
"$CCID_BIN" render --repo "$PWD" --check
proto --version
moon --version
rustc -vV
cargo --version
rustup run 1.94.0 rustc -vV
rustup run 1.94.0 cargo --version
python3 --version
node --version
bun --version
npm --version
deno --version
uv --version
"$CCID_BIN" cached --repo "$PWD" --check verify
test -s ".ccid/results/verify.jsonl"
# Registry/live-read selectors stay FRESH: `check`, never `cached`.
"$CCID_BIN" check --repo "$PWD" --check "published-npm"
"$CCID_BIN" check --repo "$PWD" --check "published-jsr"
"$CCID_BIN" check --repo "$PWD" --check "published-python"
"$CCID_BIN" check --repo "$PWD" --check "resolve-dependencies"
