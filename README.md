# WorkoutPlanner

WorkoutPlanner exports completed Garmin activities, generates or adjusts a
workout through the Codex CLI signed in with ChatGPT, and previews, uploads
or schedules the reviewed workout in Garmin Connect.

## Quick start

### 1. Clone and install

On Debian or Ubuntu, use Bash and Python 3.12 or newer. Clone with a GitHub
account that can read the repository. If you already have a checkout, open
it and pull the current `master` branch.

```bash
git clone https://github.com/googol23/WorkoutPlanner.git
cd WorkoutPlanner
bash setup/bootstrap.sh --install-codex &&
source .venv/bin/activate
```

Bootstrap installs the APT prerequisites, Python dependencies and a compatible
Codex CLI, then runs the offline tests. Use `--skip-os` if the prerequisites
are already installed. If your system Python is older, set
`WORKOUTPLANNER_PYTHON` to an installed Python 3.12+ interpreter with venv
support. CPython 3.12 on x86-64 Linux uses the repository's hashed wheel lock.

### 2. Sign in locally

```bash
export PATH="$HOME/.local/bin:$PATH"
hash -r
codex --version
codex exec --help | grep -F -- '--ignore-user-config'
codex login
codex login status
python -m workoutplanner.garmin.personal login
python upload_workouts.py --login
```

The Personal API login asks for Garmin's expiring API key in a hidden prompt
and stores it in your desktop keyring. The uploader login establishes the
separate local session used only when publishing workouts.

Choose **Sign in with ChatGPT**. The version and flag checks help confirm
the shell is using the compatible CLI, particularly if an older Snap
installation is also present. Garmin Personal API credentials stay in the desktop keyring. The publishing
session and Codex credentials are stored locally. Keep credential files out of Git.

### 3. Set your goals

Create the ignored `private/` directory and save the example below as
`private/athlete_profiles.json`. Change the goals, time and equipment to
match your situation. You can include a single profile or several.

```bash
mkdir -p -m 700 private
```

```json
{
  "running": {
    "activity_type": "running",
    "goals": "Build endurance for a 10 km run",
    "availability": "30 minutes"
  },
  "cycling": {
    "activity_type": "cycling",
    "goals": "Prepare for multi-day bikepacking",
    "availability": "90 minutes",
    "equipment": "Outdoor cross bike"
  },
  "strength": {
    "activity_type": "strength_training",
    "goals": "Build full-body strength",
    "availability": "60 minutes",
    "equipment": "Gym with dumbbells, a bench and cable machines"
  }
}
```

### 4. Sync and generate

From the repository root with `.venv` active:

```bash
activity_range=$(python -c 'from datetime import date, timedelta; d = date.today(); print(f"{d - timedelta(days=13)}..{d}")')
python download_activities.py --source personal --activity-type all --time-range "$activity_range" \
  --output private/recent_activities.json &&
python -m workoutplanner.chatgpt.week \
  --activities private/recent_activities.json \
  --profiles private/athlete_profiles.json
```

The planner considers the last 14 calendar days across sports and generates
options for the next seven days. It runs when you invoke it. The output path
under `private/weekly/` contains a plan per usable profile and a
`rationale.txt` explaining priorities and how to space multiple sessions.
Review the rationale before choosing a workout. If no usable workout is
available for a profile, the rationale explains the deferral.

### 5. Preview the workout you choose

Replace `RUN_DIRECTORY` with the folder name printed by generation:

```bash
python upload_workouts.py private/weekly/RUN_DIRECTORY/running.json --dry-run
```

Run the same command without `--dry-run` to upload that workout. To upload
all workouts and replace the previous managed batch, see
[managed publication](docs/workflow.md#replace-the-previous-garmin-batch).
After completing a workout and syncing your watch, repeat step 4.

## Supported activities

| Activity | Planning and Garmin upload |
| --- | --- |
| [Running](docs/activities/running.md) | Timed steps, repeats, pace or heart-rate targets |
| [Cycling](docs/activities/cycling.md) | Timed steps, effort cues and optional watt ranges |
| [Gym strength](docs/activities/strength_training.md) | Catalog exercises, sets, reps, rests and optional loads |
| [Bouldering](docs/activities/bouldering.md) | Activity export only |

See the [workflow reference](docs/workflow.md) for input formats, private
outputs, debugging, and upload limits. The single-profile commands
`build_planning_input.py` and `generate_next_workout.py` remain available.
On other platforms, install Python dependencies in an environment with
`python -m pip install -r requirements.txt` and install Codex separately.

## Upload and schedule

Review the workout and its rationale first. Upload alone creates a workout
template. To schedule, add `"scheduled_date": "YYYY-MM-DD"` to each workout
you want on the calendar and check that the date appears in the dry-run.

```bash
python upload_workouts.py next_workout.json
```

For calendar placement:

```bash
python upload_workouts.py next_workout.json --dry-run --schedule &&
python upload_workouts.py next_workout.json --schedule
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
| `workoutplanner/garmin/` | Personal API reader, local workout encoder, and Garmin publishing adapter |
| `workoutplanner/chatgpt/` | Compact prompt construction and authenticated generation |
| `workoutplanner/planning_input.py`, `workoutplanner/workout_schema.py` | Shared JSON input and plan validation |
| `skills/workout-planner/` | Shared skill, sport subskills, evidence and local exercise catalog |
| `setup/`, `tests/` | Bootstrap, pinned dependency and offline tests |
| `android/` | Native Android profile editor and mobile-app development plan |

The root Python scripts are the CLI entry points. To verify locally:

```bash
python -m unittest discover -s tests -v
python upload_workouts.py running_plan.json --dry-run
```

## Coordinate workouts across sports

Keep named profiles for running, cycling, and strength and build all next-workout
options in one local command. The planner ranks the options and explains how
to space them if you do more than one. The [multi-sport workflow](docs/workflow.md#local-multi-sport-planning)
shows the profile format, date-range export, and generation command.

Activity downloads use Garmin's Personal API client in WorkoutPlanner. The garminconnect package is used by the workout publisher. See the [Personal API setup](docs/garmin-personal.md) for credentials and standalone reader setup.

## Android app

The Android app is a separate Kotlin project under [`android/`](android/). It
edits and exchanges the same `athlete_profiles.json` format used by the local
Python runner and can test Garmin Personal API access with an encrypted key and
preview recent activity summaries. It does not replace or modify the local
pipeline. Full activity sync, workout generation and upload remain planned. See
the [Android app plan](docs/android-app.md) for status and account-access
prerequisites.
