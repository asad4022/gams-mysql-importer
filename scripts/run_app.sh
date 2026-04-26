#!/usr/bin/env bash
set -euo pipefail

# Launch the stable GUI with the local virtual environment when available.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/.." && pwd)"

cd "${project_root}"

if [[ -x ".venv/bin/python" ]]; then
    exec ".venv/bin/python" -m app.gui_importer
fi

if command -v python3 >/dev/null 2>&1; then
    exec python3 -m app.gui_importer
fi

if command -v python >/dev/null 2>&1; then
    exec python -m app.gui_importer
fi

echo "Python was not found."
echo "Run ./scripts/setup_macos.sh first, or activate a Python 3.11 environment before launching the app."
exit 1
