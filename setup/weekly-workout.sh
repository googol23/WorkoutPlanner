#!/usr/bin/env bash
# Runs on a fresh GitHub-hosted runner.
set -euo pipefail
umask 077

garmin_secret=${GARMIN_TOKENS_JSON:-}
codex_secret=${CODEX_AUTH_JSON:-}
athlete_secret=${ATHLETE_PROFILE_JSON:-}
unset GARMIN_TOKENS_JSON CODEX_AUTH_JSON ATHLETE_PROFILE_JSON
if [[ -z "$garmin_secret" || -z "$codex_secret" || -z "$athlete_secret" ]]; then
    printf '%s\n' 'Set GARMIN_TOKENS_JSON, CODEX_AUTH_JSON, and ATHLETE_PROFILE_JSON in Actions secrets.' >&2
    exit 1
fi

run_dir=$(mktemp -d)
auth_file="$HOME/.codex/auth.json"
if [[ -e "$auth_file" || -L "$auth_file" ]]; then
    rmdir -- "$run_dir"
    printf '%s\n' 'Expected a fresh runner without a Codex login cache.' >&2
    exit 1
fi
cleanup() {
    rm -f -- "$auth_file"
    rm -rf -- "$run_dir"
}
trap cleanup EXIT
token_dir="$run_dir/garmin"
profile="$run_dir/athlete.json"
log="$run_dir/run.log"
mkdir -p -- "$token_dir" "$HOME/.codex"

write_json_secret() {
    local value=$1 name=$2 destination=$3
    if ! printf '%s' "$value" | python -c '
import json
import sys
from pathlib import Path

data = json.load(sys.stdin)
if not isinstance(data, dict) or not data:
    raise ValueError("Expected a nonempty JSON object")
with Path(sys.argv[1]).open("x", encoding="utf-8") as stream:
    json.dump(data, stream)
' "$destination" >>"$log" 2>&1; then
        printf '%s must contain a valid JSON object.\n' "$name" >&2
        exit 1
    fi
}

write_json_secret "$garmin_secret" GARMIN_TOKENS_JSON "$token_dir/garmin_tokens.json"
write_json_secret "$athlete_secret" ATHLETE_PROFILE_JSON "$profile"
unset garmin_secret athlete_secret

run_step() {
    local name=$1
    shift
    printf '%s\n' "$name"
    if "$@" </dev/null >>"$log" 2>&1; then
        return
    else
        local status=$?
        printf '%s failed (exit %s). Details withheld from Actions logs.\n' "$name" "$status" >&2
        exit "$status"
    fi
}

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if ! sport=$(python -c '
import json, sys
from pathlib import Path
sport = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("activity_type")
if sport not in ("running", "cycling", "strength_training"):
    raise ValueError("Unknown sport")
print(sport)
' "$profile" 2>>"$log"); then
    printf '%s\n' 'Set activity_type to running, cycling, or strength_training in ATHLETE_PROFILE_JSON.' >&2
    exit 1
fi

run_step 'Sync Garmin history' env WORKOUTPLANNER_GARMIN_NONINTERACTIVE=1 \
    WORKOUTPLANNER_GARMIN_TOKEN_DIR="$token_dir" python download_activities.py \
    --activity-type all --limit 20 --output "$run_dir/activities.json"
# Keep the updated Garmin login out of files during model generation.
garmin_secret=$(< "$token_dir/garmin_tokens.json")
rm -f -- "$token_dir/garmin_tokens.json"
run_step 'Build planning input' python build_planning_input.py \
    --activities "$run_dir/activities.json" --athlete "$profile" \
    --activity-type "$sport" --output "$run_dir/planning_input.json"

write_json_secret "$codex_secret" CODEX_AUTH_JSON "$auth_file"
unset codex_secret
run_step 'Generate workout' python generate_next_workout.py \
    --planning-input "$run_dir/planning_input.json" --output "$run_dir/next_workout.json"
rm -f -- "$auth_file"
run_step 'Validate Garmin workout' python upload_workouts.py "$run_dir/next_workout.json" --dry-run

if [[ "${WORKOUTPLANNER_UPLOAD:-false}" == true ]]; then
    write_json_secret "$garmin_secret" GARMIN_TOKENS_JSON "$token_dir/garmin_tokens.json"
    unset garmin_secret
    run_step 'Upload workout to Garmin' env WORKOUTPLANNER_GARMIN_NONINTERACTIVE=1 \
        WORKOUTPLANNER_GARMIN_TOKEN_DIR="$token_dir" python upload_workouts.py "$run_dir/next_workout.json"
fi
printf '%s\n' 'Workout pipeline completed.'
