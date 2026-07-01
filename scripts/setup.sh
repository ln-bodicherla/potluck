#!/usr/bin/env bash
# Set up Potluck (the CLI) and check the prerequisites for exo (the engine).
#
# We install the `potluck` CLI reliably into a project venv. exo itself is a
# heavier install (verified against exo `main`, 2026) — it is NOT `pip install exo`.
# exo needs Python 3.13, uv, node, Rust, macmon, and Xcode's Metal toolchain, then a
# clone + dashboard build. This script installs Potluck and then tells you exactly
# what exo still needs, with the real commands, rather than guessing.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Installing the Potluck CLI into a virtualenv"
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ and re-run." >&2
  exit 1
fi
python3 -m venv "$here/.venv"
"$here/.venv/bin/python" -m pip install -q --upgrade pip
# Non-editable install: reliable on all Python versions. (hatchling's editable .pth
# is not honored on Python 3.14; contributors who want live edits can instead run
# `PYTHONPATH=src .venv/bin/python -m potluck.cli ...` or reinstall after changes.)
"$here/.venv/bin/python" -m pip install -q --no-cache-dir "$here"
echo "    OK: $here/.venv/bin/potluck"
echo "    Add it to PATH for this shell:  export PATH=\"$here/.venv/bin:\$PATH\""

echo
echo "==> Checking exo prerequisites"
missing=0
check() { if command -v "$1" >/dev/null 2>&1; then echo "    ✓ $1"; else echo "    ✗ $1 — $2"; missing=1; fi; }

# exo pins Python ==3.13.*  (uv will manage this for you if installed)
if command -v python3.13 >/dev/null 2>&1; then
  echo "    ✓ python3.13"
else
  echo "    ✗ python3.13 — exo requires exactly 3.13 (uv can provide it: 'uv python install 3.13')"
  missing=1
fi
check uv    "install with: brew install uv"
check node  "install with: brew install node   (needed to build exo's dashboard)"
check cargo "install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh && rustup toolchain install nightly"
check xcodebuild "install Xcode from the App Store (provides the Metal toolchain for MLX)"

echo
if [ "$missing" -eq 0 ]; then
  cat <<'EOF'
==> All exo prerequisites present. Install & run exo:
      git clone https://github.com/exo-explore/exo
      cd exo/dashboard && npm install && npm run build && cd ..
      uv run exo                 # API + dashboard at http://localhost:52415
    Then, from Potluck:
      potluck up --mode split --devices mac32,mac16   # prints the exo command to run
      potluck bench <model> --url http://localhost:52415/v1 --calibrate <device>
EOF
else
  echo "==> Install the missing prerequisites above, then re-run this script."
  echo "    Full exo instructions: https://github.com/exo-explore/exo#quick-start"
fi
