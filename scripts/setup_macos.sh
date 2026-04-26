#!/usr/bin/env bash
set -euo pipefail

# Set up the stable importer with Python 3.11 and verify tkinter early.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_root="$(cd "${script_dir}/.." && pwd)"
venv_path="${project_root}/.venv"

find_python() {
    local candidate version
    for candidate in python3.11 python3 python; do
        if ! command -v "${candidate}" >/dev/null 2>&1; then
            continue
        fi

        version="$("${candidate}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
        if [[ "${version}" == "3.11" ]]; then
            printf '%s\n' "${candidate}"
            return 0
        fi
    done

    return 1
}

python_cmd="$(find_python || true)"
if [[ -z "${python_cmd}" ]]; then
    echo "Python 3.11 was not found."
    echo "Install Python 3.11 first. On macOS, Python from python.org is recommended so tkinter is included."
    exit 1
fi

if ! "${python_cmd}" -c 'import tkinter' >/dev/null 2>&1; then
    echo "Python 3.11 is installed, but tkinter is unavailable."
    echo "Install Python 3.11 from python.org and rerun this setup script."
    exit 1
fi

venv_python="${venv_path}/bin/python"
if [[ -x "${venv_python}" ]]; then
    existing_version="$("${venv_python}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [[ "${existing_version}" != "3.11" ]]; then
        case "${venv_path}" in
            "${project_root}"/*)
                echo "Existing virtual environment uses Python ${existing_version}. Recreating with Python 3.11..."
                rm -rf "${venv_path}"
                ;;
            *)
                echo "Refusing to remove virtual environment outside project root: ${venv_path}"
                exit 1
                ;;
        esac
    fi
fi

if [[ ! -d "${venv_path}" ]]; then
    "${python_cmd}" -m venv "${venv_path}"
fi

"${venv_python}" -m pip install --upgrade pip
"${venv_python}" -m pip install -r "${project_root}/requirements.txt"

if command -v gams >/dev/null 2>&1; then
    echo "Detected GAMS on PATH: $(command -v gams)"
else
    echo "GAMS was not found on PATH."
    echo "If GAMS is installed, create config/app_config.json from config/app_config.example.json and set gams_executable."
fi

echo
echo "Environment setup complete."
echo "Activate with: source .venv/bin/activate"
echo "Verify tkinter with: .venv/bin/python -c \"import tkinter; print('tkinter ok')\""
echo "Verify GAMS with: command -v gams"
echo "Run with: ./scripts/run_app.sh"
