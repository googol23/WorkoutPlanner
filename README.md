# Garmin Connect JSON workout uploader and activity exporter

Imports running workouts from an application-level JSON file, converts them to Garmin's typed running workout format, and optionally schedules them. The separate read-only exporter downloads completed activities as JSON for external analysis. Neither tool generates plans or performs fitness analysis. Uses the unofficial [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) API; Garmin can change its service without notice.

## Setup (Python 3.12+)

The existing `.venv` can be used, or create one with `python3.12 -m venv .venv`. From this project directory:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

On Windows activate with `.venv\Scripts\activate` instead. `requirements.txt` pins `garminconnect[workout]==0.3.20` (the `workout` extra installs Pydantic). The CLI does not support the older `garth`-based 0.2.x tokens.

## Commands

Run from the project directory after installation:

```bash
python upload_workouts.py --login
python upload_workouts.py running_plan.json --dry-run
python upload_workouts.py running_plan.json --dry-run --schedule
python upload_workouts.py running_plan.json
python upload_workouts.py running_plan.json --schedule
```

**These are live account operations except dry-run.** Review the plan and obtain authorization before executing `--login`, upload or schedule. Dry-run only validates and previews; it does not contact Garmin or verify server-side duplicates. Upload alone does not schedule. Scheduling uploads missing templates and schedules only entries with `scheduled_date`.

Login uses a terminal email/password prompt (password hidden), and prompts for an MFA code if requested. It first tries reusable tokens in `~/.garminconnect/garmin_tokens.json`; the library restricts local token permissions. Keep the token store private and outside version control. Never pass passwords or tokens in command-line arguments. Network access to Garmin is required for all non-dry-run commands.

## Export completed activities

From the same installed environment and project directory:

```bash
python download_activities.py
python download_activities.py --limit 5
python download_activities.py --activity-id 25175214513
python download_activities.py --limit 5 --output recent_runs.json
python download_activities.py --perceived-effort 7 --fatigue "tired" --pain "none" --comments "felt good"
```

The default file is `running_activities.json`. The exporter reuses the uploader's saved-token login (and prompts if tokens are missing/expired). It pages through Garmin's running activity list, checks each selected activity is a completed run, and never modifies Garmin account data. `--activity-id` and `--limit` are mutually exclusive. If fewer runs are available, it exports those found; if none are found it fails without writing a file.

To sync a date range or select another sport:

```bash
python download_activities.py --time-range 2026-11-16..2026-11-23 --activity-type cycling
python download_activities.py --activity-type all --limit 10 --output recent_activities.json
```

`--time-range` includes both calendar dates using the local start date recorded
by Garmin for each activity. It is mutually exclusive with `--limit` and
`--activity-id`. Garmin's date query handles pagination. Within each export,
repeated activity IDs are emitted once. The output is a snapshot and replaces
the target file when results are available. If no matching activities are
found, the command exits with an error and leaves any existing file intact.

`--activity-type` defaults to `running` and accepts `all` or an exact Garmin
`typeKey` from the activity's `activityType` or `activityTypeDTO` object. A parent sport key does not
automatically select its subtypes. Use `all` and inspect the reported type keys
when a subtype is unknown. The default output is `<activity-type>_activities.json`,
including `all_activities.json` for mixed sports.

The single JSON document has `schema_version`, UTC `exported_at`, and `activities`. Each activity includes `activity_id`, `activity_name`, `activity_date`, `summary`, `splits`, `workout_steps`, `heart_rate_zones`, `power_zones`, `time_series`, `weather`, `subjective_feedback`, and `unavailable_fields`. Original metric values, timestamps, and units are retained where returned. `time_series` pairs Garmin metric descriptors (including units when provided) with sample values keyed by descriptor name. Garmin's default detail chart limit is 2,000 points, so longer runs may have downsampled series; the exporter requests no route polyline. Optional endpoints returning no data or 404 yield `null` and a name in `unavailable_fields`; other API failures stop the export. Feedback is optional: `--perceived-effort` must be 1–10; `--fatigue`, `--pain`, and `--comments` accept text and apply to every exported run. For individual feedback per run, export each run separately.

Structured GPS/location fields, personal identifiers and credentials are removed recursively; location sample descriptors are omitted. **Review activity names, feedback and any other free text before sharing**: user-entered text may still contain identifying information. Treat exported activity data as private and share it with ChatGPT only if you intend to. ChatGPT can analyze the export and produce updated workout JSON files; this project does not do that analysis.

## JSON input

The supplied `running_plan.json` is the reference format. Top-level fields: `schema_version: "1.0"`, `sport: "running"`, `timezone` (informational IANA timezone), `units: {"duration": "seconds", "pace": "seconds_per_km", "heart_rate": "bpm"}`, and a nonempty `workouts` array. Each workout needs a unique `name`, positive integer `week`, `total_duration_seconds` matching expanded steps, and nonempty `steps`; `description` and `scheduled_date` (`YYYY-MM-DD`) are optional. `timezone` does not shift date-only calendar entries; Garmin schedules by the provided date.

Step forms:

```json
{"type": "warmup", "duration_seconds": 600, "target": {"type": "none"}}
{"type": "run", "duration_seconds": 60, "target": {"type": "pace", "fast_seconds_per_km": 360, "slow_seconds_per_km": 385}}
{"type": "recovery", "duration_seconds": 120, "target": {"type": "heart_rate", "min_bpm": 110, "max_bpm": 130}}
{"type": "cooldown", "duration_seconds": 300}
{"type": "repeat", "count": 6, "steps": [{"type": "run", "duration_seconds": 60}]}
```

`interval` is an alias for `run`. Omit `target` or use `{ "type": "none" }` for untargeted steps. All timed steps support pace, heart-rate, and no-target modes, plus an optional nonempty `description`. Pace limits convert from seconds/km to m/s; slower pace becomes the lower Garmin speed. Repeats are Garmin repeat groups with globally unique step orders. Unsupported fields and invalid targets fail before login/upload.

## Duplicate behavior and limits

On each live invocation the script pages through your Garmin workout library and skips an existing **identically named** template (names serve as identifiers, not a content checksum). Multiple templates with the same name stop processing. If an existing template's contents were changed, the script does not update it; review it manually. For scheduling it loads the affected months' calendar entries and skips an existing `(workoutId, date)` pair. It stops on an unrecognized calendar response rather than risking duplicates. No local database or token files are written to the project. An upload with an ambiguous/failed response may nevertheless have succeeded: check the Garmin workout library before retrying. API requests are not atomic, and concurrent runs or Garmin's delayed calendar visibility can still cause duplicates; do not run two copies simultaneously. The script does not modify or remove existing workouts or calendar entries.

Unit tests use mocked library objects/API responses and make **no live Garmin requests**. The installed dependency's real API and account behavior cannot be confirmed without a separately authorized live test.

## Build planning input

Create an `athlete.json` file with your own context. The required fields are
`goals` and `availability`. Optional fields are `constraints`, `preferences`,
and `recent_feedback`. Each field is nonempty text.

```json
{
  "goals": "Build endurance for a 10 km run",
  "availability": "30 minutes for the next workout",
  "preferences": "Outdoor route",
  "recent_feedback": "The last easy run felt comfortable"
}
```

```bash
python build_planning_input.py --activities all_activities.json --athlete athlete.json --activity-type running > planning_input.json
```

The builder writes a JSON object with `schema_version: "1.0"`,
`target_activity_type`, `athlete`, and `activity_history`. The target names
the next workout, so the history can include multiple sports. The builder keeps
the exported summaries, splits, workout steps, heart-rate and power zones,
sample descriptors and values, weather, subjective feedback, and missing-field
markers as supplied. It carries through Garmin's chart sampling limits.
The activity context documents describe sport-specific coverage.

The builder runs locally. Review athlete notes and activity names before
sharing the result, and keep personal exports and athlete context out of Git.

## Prepare the WorkoutPlanner prompt

Build a single prompt containing the shared skill, selected sport subskill,
linked research, output format, and your planning input. Supported planning
targets are `running`, `cycling`, and `strength_training`. Set the target with
`--activity-type` when building the planning input.

```bash
python build_chatgpt_prompt.py --planning-input planning_input.json > workout_prompt.md
```

To adjust an existing session, provide its exact workout name:

```bash
python build_chatgpt_prompt.py --planning-input planning_input.json \
  --existing-plan running_plan.json --workout-name "Example running workout" > workout_prompt.md
```

Review `workout_prompt.md` before pasting it into ChatGPT. It contains the
athlete context and a compact activity history, plus the selected workout when
adjusting a plan. The command runs offline. Keep the generated prompt and the
personal inputs out of Git.

Paste the prompt into ChatGPT and wait for a response. For running, review the
rationale, then copy the contents of the workout JSON block into a new local
file named `next_workout.json`. The prompt builder creates the prompt only.
Once the workout file exists, validate it offline with the Garmin uploader:

```bash
python upload_workouts.py next_workout.json --dry-run
```

Cycling uses its own timed-step format and can also be previewed and uploaded
with the Garmin uploader. Strength plans are for manual use.

## Generate directly with your ChatGPT account

Install the [Codex CLI](https://learn.chatgpt.com/docs/cli) and sign in with
your ChatGPT account. To run login without environment proxies:

```bash
env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u FTP_PROXY \
    -u http_proxy -u https_proxy -u all_proxy -u ftp_proxy \
    codex login
codex login status
```

Run the generator with the planning input you already built:

```bash
python generate_next_workout.py --planning-input planning_input.json
```

This sends the prompt and athlete history directly through the Codex CLI
using your ChatGPT account. It removes proxy environment variables from
the Codex subprocess and uses an ephemeral Codex session. Review the data
in the planning input before running it. The command prints the rationale,
checks the response against the selected sport, and writes
`next_workout.json` only when a workout is returned and passes validation.
Running and cycling use the uploader's full validation. Strength plans
receive basic format and sport checks and are for manual use.

The generator also accepts `--existing-plan` and `--workout-name` together
to adjust a named session. Use `--output` to choose a different destination.
Review a generated running workout with:

```bash
python upload_workouts.py next_workout.json --dry-run
```

If Codex generation fails, rerun the generator with `--debug` to see
the CLI error. Review the diagnostics before sharing them. The generator
keeps an existing workout file intact when generation fails.

### Prompt size

Both prompt paths use the same 24 KB UTF-8 budget, including sport instructions
and evidence. They keep up to 12 recent summaries, prioritizing the target sport and
including up to three other activities for recovery context. They keep selected summary metrics, zone totals,
the first six available splits, available exercise-set summaries, and brief
per-session feedback. Raw chart samples stay in your local planning input.
The prompt indicates that activity coverage is partial.

If the athlete notes or selected workout still cause the prompt to exceed the
budget, shorten them and rerun. The generator checks the size before calling
Codex. Existing exports and planning inputs work with the new prompt builder.

### Preview a cycling workout

Use a separate profile, such as `athlete_cycling.json`, with a cycling goal.
For example:

```json
{
  "activity_type": "cycling",
  "goals": "Build cycling endurance for longer weekend rides",
  "availability": "30 minutes for my next ride",
  "training_background": "I typically ride 30 to 45 minutes at an easy effort"
}
```

Replace the example with your own goal and recent riding experience. Optional
`equipment` and `benchmarks` fields can describe indoor or outdoor setup,
a recent FTP, or known zones. Use the matching `activity_type` in the profile
for cycling or gym strength. Existing untagged running profiles still work.

```bash
python build_planning_input.py --activities all_activities.json \
  --athlete athlete_cycling.json --activity-type cycling > cycling_input.json &&
python generate_next_workout.py --planning-input cycling_input.json --output next_ride.json &&
python upload_workouts.py next_ride.json --dry-run
```

Cycling steps carry an effort cue and may include a supported watt range.
After reviewing the preview, use the same uploader without `--dry-run`
to create the Garmin workout. Scheduling is optional with `--schedule` and
an explicit `scheduled_date` on the workout.

### Prepare a gym workout

For Garmin activities with the exact `strength_training` type, the exporter
also requests recorded exercise sets. Missing or empty set data is marked
unavailable. Use a profile such as `athlete_strength.json` with
`"activity_type": "strength_training"`, your strength or hypertrophy goal,
available time, and the equipment and training background you want the
planner to consider.
