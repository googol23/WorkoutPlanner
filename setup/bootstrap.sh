#!/usr/bin/env bash
# Bootstrap WorkoutPlanner from an existing clone.
set -euo pipefail

install_os=true
install_codex=false
reader_only=false
for arg in "$@"; do
    case "$arg" in
        --reader-only) reader_only=true ;;
        --skip-os) install_os=false ;;
        --install-codex) install_codex=true ;;
        --skip-codex) install_codex=false ;;
        -h|--help)
            printf '%s\n' 'Usage: bash setup/bootstrap.sh [--reader-only] [--skip-os] [--install-codex|--skip-codex]'
            exit 0 ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

# Apply direct connections to the installer and its child processes.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY http_proxy https_proxy all_proxy ftp_proxy
unset PIP_PROXY

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${WORKOUTPLANNER_PYTHON:-python3}
if "$reader_only"; then
    mkdir -p -m 700 "$repo_dir/private"
    venv_dir=${WORKOUTPLANNER_VENV:-"$repo_dir/private/reader-venv"}
else
    venv_dir=${WORKOUTPLANNER_VENV:-"$repo_dir/.venv"}
fi

if "$install_os"; then
    if ! command -v apt-get >/dev/null; then
        printf '%s\n' 'OS setup supports Debian and Ubuntu. Install Git, curl, CA certificates, and Python 3.12+ with venv, then rerun with --skip-os.' >&2
        exit 1
    fi
    apt=(apt-get)
    if (( EUID != 0 )); then
        apt=(sudo env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u FTP_PROXY
             -u http_proxy -u https_proxy -u all_proxy -u ftp_proxy apt-get)
    fi
    apt_options=(-o Acquire::http::Proxy=DIRECT -o Acquire::https::Proxy=DIRECT)
    "${apt[@]}" "${apt_options[@]}" update
    "${apt[@]}" "${apt_options[@]}" install -y git curl ca-certificates python3 python3-venv
fi

if ! "$python_bin" -c 'import sys; raise SystemExit(sys.version_info < (3, 12))'; then
    printf '%s\n' 'Install Python 3.12 or newer with venv, then rerun with WORKOUTPLANNER_PYTHON set to that interpreter.' >&2
    exit 1
fi
"$python_bin" -m venv "$venv_dir"
requirements="$repo_dir/setup/requirements-garmin.txt"
if "$reader_only"; then
    requirements="$repo_dir/setup/requirements-fit-check.txt"
    if ! "$venv_dir/bin/python" -c 'from importlib.util import find_spec; raise SystemExit(find_spec("garminconnect") is not None)'; then
        printf '%s\n' 'Choose a clean reader environment with WORKOUTPLANNER_VENV. This one can import garminconnect.' >&2
        exit 1
    fi
elif "$venv_dir/bin/python" -c 'import platform, sys; raise SystemExit(not (platform.python_implementation() == "CPython" and sys.version_info[:2] == (3, 12) and sys.platform == "linux" and platform.machine() == "x86_64"))'; then
    requirements="$repo_dir/setup/requirements-linux-x86_64-py312.lock"
fi
PIP_CONFIG_FILE=/dev/null "$venv_dir/bin/python" -m pip install --only-binary=:all: -r "$requirements"

codex_supported() {
    local help_text
    help_text=$(codex exec --help 2>/dev/null) &&
        [[ "$help_text" == *--ignore-user-config* &&
           "$help_text" == *--ephemeral* &&
           "$help_text" == *--output-schema* &&
           "$help_text" == *--output-last-message* ]]
}

if "$install_codex"; then
    export PATH="$HOME/.local/bin:$PATH"
    if ! codex_supported; then
        codex_installer=$(mktemp)
        trap 'rm -f -- "$codex_installer"' EXIT
        curl -fsSL --proto '=https' --proto-redir '=https' https://chatgpt.com/codex/install.sh -o "$codex_installer"
        sh "$codex_installer" </dev/null
        hash -r
    fi
    if ! codex_supported; then
        printf '%s\n' 'Codex is missing required exec options. Verify the installed binary and PATH.' >&2
        exit 1
    fi
    codex --version
    printf '%s\n' 'In your current shell, run: export PATH="$HOME/.local/bin:$PATH"'
fi

venv_dir=$(cd -- "$venv_dir" && pwd)
cd -- "$repo_dir"
if "$reader_only"; then
    for suite in test_personal_api.py test_personal_reader.py test_fit_check.py test_endurance_fit.py test_week_planning.py; do
        "$venv_dir/bin/python" -m unittest discover -s tests -p "$suite"
    done
else
    "$venv_dir/bin/python" -m unittest discover -s tests
fi
printf 'Activate the environment with: source %q\n' "$venv_dir/bin/activate"
