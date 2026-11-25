# WorkoutPlanner

WorkoutPlanner exports completed Garmin activities, generates or adjusts a
workout through the Codex CLI signed in with ChatGPT, and previews, uploads
or schedules the reviewed workout in Garmin Connect.

| Activity | Planning and Garmin upload | Live checks reported |
| --- | --- | --- |
| [Running](docs/activities/running.md) | Timed steps, repeats, pace or heart-rate targets | Generation, preview, upload and duplicate upload detection |
| [Cycling](docs/activities/cycling.md) | Timed steps, effort cues and optional watt ranges | Generation, preview and detection of an existing upload |
| [Gym strength](docs/activities/strength_training.md) | Catalog exercises, sets, reps, timed rests and optional loads | Exercise-set export, generation, preview, upload, scheduling and both duplicate checks |
| [Bouldering](docs/activities/bouldering.md) | Activity export only | A mixed export contained the `bouldering` type |

Run the workflow locally or configure the [weekly GitHub Actions workflow](docs/weekly-workout.md)
on a private, dedicated runner. See the [workflow reference](docs/workflow.md)
for data formats, troubleshooting and operational limits.

## Setup

From an existing clone on Debian or Ubuntu with Python 3.12 or newer:

```bash
bash setup/bootstrap.sh
source .venv/bin/activate
```

Bootstrap installs system prerequisites through APT, creates the environment,
installs the pinned `garminconnect[workout]==0.3.20` dependency, and runs
offline tests. Pass `--install-codex` to opt in to the official Codex installer. It disables proxies for its network commands.
Use `--skip-os` with preinstalled dependencies or `--skip-codex` for Garmin
only (the default). On systems with an older default Python, set `WORKOUTPLANNER_PYTHON` to
an installed Python 3.12+ interpreter. Other platforms can install the Python
dependencies with `python -m pip install -r requirements.txt`.

For Bash, the following helper runs network commands without proxy environment
variables. Git also clears its configured proxy in the example below.

```bash
direct() {
  env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u FTP_PROXY \
      -u http_proxy -u https_proxy -u all_proxy -u ftp_proxy "$@"
}
direct git -c http.proxy= -c remote.origin.proxy= pull --ff-only origin master
direct codex login
```

Choose ChatGPT sign-in. Garmin login reuses saved tokens when present and may
prompt for credentials and MFA when needed. The generator clears proxy
environment variables in its Codex subprocess automatically.

## Generate and preview

Export your history first. This example gathers up to ten completed activities
across sports:

```bash
direct python download_activities.py --activity-type all --limit 10 --output all_activities.json
```

Create `athlete.json` for running and use your own goal and time budget:

```json
{
  "activity_type": "running",
  "goals": "Build endurance for a 10 km run",
  "availability": "30 minutes for the next workout"
}
```

```bash
python build_planning_input.py --activities all_activities.json \
  --athlete athlete.json --activity-type running --output planning_input.json &&
python generate_next_workout.py --planning-input planning_input.json &&
python upload_workouts.py next_workout.json --dry-run
```

Use `cycling` or `strength_training` as the target with a matching
sport-specific profile. The [strength profile guide](docs/activities/strength_training.md)
includes an equipment and exercise preference example. For manual ChatGPT
handoff, use `build_chatgpt_prompt.py` and review the prompt before sharing it.

## Upload and schedule

Review the workout and its rationale first. Upload alone creates a workout
template. To schedule, add `"scheduled_date": "YYYY-MM-DD"` to each workout
you want on the calendar and check that the date appears in the dry-run.

```bash
direct python upload_workouts.py next_workout.json
```

For calendar placement:

```bash
python upload_workouts.py next_workout.json --dry-run --schedule &&
direct python upload_workouts.py next_workout.json --schedule
```

An exact existing workout name is skipped. Scheduling also skips an existing
workout ID and date pair. Check Garmin Connect before retrying an ambiguous
failure. Keep credentials and personal files out of Git. Use an ignored `private/`
directory for custom filenames. Choose `--output` on the input and prompt
builders for atomic private files on POSIX. The generator saves rationale
beside the workout instead of printing it.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `workoutplanner/garmin/` | Separate read and write tools, shared Garmin authentication, and strength conversion |
| `workoutplanner/chatgpt/` | Compact prompt construction and authenticated generation |
| `workoutplanner/planning_input.py`, `workoutplanner/workout_schema.py` | Shared JSON input and plan validation |
| `skills/workout-planner/` | Shared skill, sport subskills, evidence and local exercise catalog |
| `setup/`, `tests/` | Bootstrap, pinned dependency and offline tests |

The root Python scripts are the CLI entry points. To verify locally:

```bash
python -m unittest discover -s tests -v
python upload_workouts.py running_plan.json --dry-run
```
