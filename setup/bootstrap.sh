#!/usr/bin/env bash
# Bootstrap WorkoutPlanner from an existing clone.
set -euo pipefail

install_os=true
install_codex=true
for arg in "$@"; do
    case "$arg" in
        --skip-os) install_os=false ;;
        --skip-codex) install_codex=false ;;
        -h|--help)
            printf '%s\n' 'Usage: bash setup/bootstrap.sh [--skip-os] [--skip-codex]'
            exit 0 ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

# Apply direct connections to the installer and its child processes.
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY http_proxy https_proxy all_proxy ftp_proxy
unset PIP_PROXY

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${WORKOUTPLANNER_PYTHON:-python3}
venv_dir=${WORKOUTPLANNER_VENV:-"$repo_dir/.venv"}

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
PIP_CONFIG_FILE=/dev/null "$venv_dir/bin/python" -m pip install -r "$repo_dir/setup/requirements-garmin.txt"

if "$install_codex" && ! command -v codex >/dev/null; then
    curl -fsSL https://chatgpt.com/codex/install.sh | sh
fi

(cd -- "$repo_dir" && "$venv_dir/bin/python" -m unittest discover -s tests)
printf 'Activate the environment with: source %q\n' "$venv_dir/bin/activate"
