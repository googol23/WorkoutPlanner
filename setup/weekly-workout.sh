#!/usr/bin/env bash
# Runs on the dedicated runner under its own OS account.
set -euo pipefail
umask 077
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY http_proxy https_proxy all_proxy ftp_proxy

local_dir="$HOME/.local/share/workoutplanner"
python_bin="$local_dir/venv/bin/python"
profile="$local_dir/athlete.json"
if [[ ! -x "$python_bin" || ! -r "$profile" ]]; then
    printf '%s\n' 'Runner setup is incomplete. See docs/weekly-workout.md.' >&2
    exit 1
fi
mkdir -p -- "$local_dir/runs"
run_dir=$(mktemp -d "$local_dir/runs/run.XXXXXXXX")
log="$run_dir/run.log"

run_step() {
    local name=$1
    shift
    printf '%s\n' "$name"
    if ! "$@" </dev/null >>"$log" 2>&1; then
        printf '%s failed. See the private runner log in %s.\n' "$name" "${run_dir##*/}" >&2
        exit 1
    fi
}

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if ! sport=$("$python_bin" -c '
import json, sys
from pathlib import Path

sport = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("activity_type")
if sport not in ("running", "cycling", "strength_training"):
    raise ValueError("Set activity_type to running, cycling or strength_training")
print(sport)
' "$profile" 2>>"$log"); then
    printf 'Invalid athlete profile. See the private runner log in %s.\n' "${run_dir##*/}" >&2
    exit 1
fi

run_step 'Sync Garmin history' "$python_bin" download_activities.py \
    --activity-type all --limit 20 --output "$run_dir/activities.json"
run_step 'Build planning input' "$python_bin" build_planning_input.py \
    --activities "$run_dir/activities.json" --athlete "$profile" \
    --activity-type "$sport" --output "$run_dir/planning_input.json"
run_step 'Generate workout' "$python_bin" generate_next_workout.py \
    --planning-input "$run_dir/planning_input.json" --output "$run_dir/next_workout.json"
run_step 'Validate Garmin workout' "$python_bin" upload_workouts.py \
    "$run_dir/next_workout.json" --dry-run

if [[ "${WORKOUTPLANNER_UPLOAD:-false}" == true ]]; then
    run_step 'Upload workout to Garmin' "$python_bin" upload_workouts.py "$run_dir/next_workout.json"
fi
printf 'Completed. Private runner files: %s\n' "${run_dir##*/}"
