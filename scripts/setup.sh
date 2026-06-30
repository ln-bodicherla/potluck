#!/usr/bin/env bash
# Install exo (the inference engine) and the `potluck` CLI on this machine.
# Safe to re-run. Tested target: macOS (Apple Silicon) and Linux + NVIDIA.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Checking Python (need 3.10+)"
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.10+ and re-run." >&2
  exit 1
fi
python3 - <<'PY'
import sys
assert sys.version_info >= (3, 10), f"Need Python 3.10+, have {sys.version.split()[0]}"
print("    OK:", sys.version.split()[0])
PY

echo "==> Installing the potluck CLI (editable)"
python3 -m pip install --user -e "$here"

echo "==> Installing exo (distributed-inference engine)"
if command -v exo >/dev/null 2>&1; then
  echo "    exo already installed: $(command -v exo)"
else
  # exo is distributed from source; pull and install it.
  exo_dir="${POTLUCK_EXO_DIR:-$HOME/.potluck/exo}"
  if [ ! -d "$exo_dir/.git" ]; then
    echo "    Cloning exo into $exo_dir"
    git clone https://github.com/exo-explore/exo "$exo_dir"
  else
    echo "    Updating existing exo checkout in $exo_dir"
    git -C "$exo_dir" pull --ff-only || true
  fi
  echo "    Installing exo (this can take a few minutes)"
  python3 -m pip install --user -e "$exo_dir"
fi

echo
echo "==> Done."
echo "    Next:"
echo "      potluck pool create my-house     # first machine"
echo "      potluck pool join POT-XXXX-XXXX  # the others"
echo "      potluck up                       # bring a machine online"
echo
echo "    If 'potluck' isn't found, add your user bin to PATH:"
echo "      export PATH=\"\$HOME/.local/bin:\$PATH\"   # Linux"
echo "      export PATH=\"\$(python3 -m site --user-base)/bin:\$PATH\""
