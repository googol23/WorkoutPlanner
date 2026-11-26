#!/usr/bin/env bash
# Preview or remove known disposable WorkoutPlanner outputs and Python caches.
set -euo pipefail

apply=false
case "${1:-}" in
    "") ;;
    --apply) apply=true ;;
    -h|--help)
        printf '%s\n' 'Usage: bash scripts/cleanup-local.sh [--apply]'
        printf '%s\n' 'Default mode lists candidates. --apply removes only listed generated outputs and Python caches.'
        exit 0 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
esac

repo_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_dir"

candidates=()
outputs=(
    athlete.json
    planning_input.json
    workout_prompt.md
    next_workout.json
    cycling_input.json
    next_ride.json
    strength_input.json
    next_strength.json
)

for path in "${outputs[@]}"; do
    [[ -f "$path" ]] && candidates+=("$path")
done

while IFS= read -r -d '' path; do
    candidates+=("$path")
done < <(find . -maxdepth 1 -type f \( -name 'next_*_scheduled.json' -o -name '*.json.rationale.txt' -o -name '*.json.debug.txt' \) -print0)

while IFS= read -r -d '' path; do
    candidates+=("$path")
done < <(find . -type d \( -name .git -o -name .venv -o -name private -o -name __pycache__ -o -name .pytest_cache \) -prune -print0 | while IFS= read -r -d '' path; do
    case "$path" in
        ./.git|./.venv|./private) ;;
        *) printf '%s\0' "$path" ;;
    esac
done)

if (("${#candidates[@]}" == 0)); then
    printf '%s\n' 'No cleanup candidates found.'
    exit 0
fi

if "$apply"; then
    for path in "${candidates[@]}"; do
        if git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
            printf 'Keeping tracked file: %s\n' "$path"
            continue
        fi
        rm -rf -- "$path"
        printf 'Removed: %s\n' "$path"
    done
else
    printf '%s\n' 'Cleanup preview. No files were removed.'
    printf '  %s\n' "${candidates[@]}"
    printf '%s\n' 'Run with --apply to remove these candidates.'
fi
