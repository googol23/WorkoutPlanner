# Workflow reference

## Garmin export

For normal activity sync, pass `--source personal`. This uses WorkoutPlanner's small Garmin Personal API client and the expiring personal key stored in the ignored `private/garmin_personal_api_key` file. It does not import the Garmin Connect wrapper. The default `legacy` source remains for the parity comparison documented in [Garmin Personal API](garmin-personal.md).

The exporter is read-only. Its default is the newest completed activity with
the exact `running` type key. Use `--activity-type all` for mixed history or
specify the exact Garmin key. Parent sport keys do not automatically include
subtypes. Choose one of the following selectors:

| Option | Behavior |
| --- | --- |
| `--limit N` | At most N recent matching activities |
| `--activity-id ID` | One activity that matches the selected type |
| `--time-range YYYY-MM-DD..YYYY-MM-DD` | Inclusive calendar dates using the local start date Garmin recorded |

The default destination is `<activity-type>_activities.json`. An export is a
snapshot with unique activity IDs. An empty match exits with an error and
keeps the existing file. Optional feedback flags apply to all activities in
that invocation. Use an activity ID to attach feedback to one session.

The JSON contains the export timestamp, activity IDs and dates, summaries,
splits, workout steps, zone times, weather, chart samples and feedback where
available. Strength exports also request exercise sets. Missing data from
optional endpoints can be reported as null with an unavailable-field marker.
Garmin can downsample charts to its 2,000-point detail limit and available
metrics vary by device, sport and recording. The exporter requests no route
polyline and filters known sensitive keys. Free text and other identifiers may
still appear. Treat exports as private.

## Profiles and generation

Use one profile per target. `goals` and `availability` are required text.
Optional text fields are `constraints`, `preferences`, `recent_feedback`,
`training_background`, `benchmarks`, and `equipment`. Cycling and strength
require `activity_type` to match the target. Existing untagged running profiles
remain valid. Strength also accepts `preferred_machines` and
`preferred_exercises` as arrays of strings.

Planning input schema 1.0 retains the complete exported activity history for
local use. The model prompt uses a separate compact view. It has a 24 KB UTF-8
budget and includes up to 12 recent summaries with up to three other-sport
sessions for recovery context. It selects a small set of sport-specific summary metrics, non-zero zone
times, up to three split rows and up to eight available strength exercise
sets. It leaves out Garmin IDs, activity metadata, raw chart samples, empty
zones, unavailable-field listings and unrelated summary fields. It sends
session numbers and calendar dates in place of Garmin IDs and exact timestamps. Raw chart
samples stay local. This is partial history and missing values are unknown.

The generator submits the prompt through an ephemeral `codex exec` session
using ChatGPT sign-in. It needs network access and available account allowance.
It saves the rationale beside the workout as `<output>.rationale.txt` and
writes a validated workout JSON only when the response contains a plan. Review the output for training suitability, schedule
and equipment. Exercise catalog resolution is checked by WorkoutPlanner's local encoder before the workout is saved.

To adjust a named workout, supply `--existing-plan PLAN.json --workout-name NAME`
to either prompt builder or generator. Use `--output` to keep the generated
plan in a separate file. For offline prompt review use:

```bash
python build_chatgpt_prompt.py --planning-input planning_input.json --output workout_prompt.md
```

Without `--output`, this command writes the prompt to standard output. For a manual ChatGPT handoff,
save the returned workout object by itself before calling the uploader.

## Upload formats and limits

| Sport | Plan reference | Conversion |
| --- | --- | --- |
| Running | [Output contract](../skills/workout-planner/references/running-output.md) and [sample plan](../running_plan.json) | Timed steps and repeats with optional pace or heart-rate targets |
| Cycling | [Cycling subskill](../skills/workout-planner/subskills/cycling/SKILL.md) | Timed steps with effort cues and optional watt ranges |
| Strength | [Strength subskill](../skills/workout-planner/subskills/strength_training/SKILL.md) | Exact Garmin exercise names, rep targets, between-set rests and optional kg or lb loads |

Strength uses the lower end of a rep range as the device target. The rest of
the range and effort cue are stored in notes. Warmup is a workout note.
A dry-run validates JSON and conversion offline. It cannot verify Garmin
account state or device display.

Live upload deduplicates by exact workout name. It does not compare content,
replace templates, or delete them. Duplicate names already in the library
cause an error. Use a distinct name for a revised template. Scheduling
requires an explicit `scheduled_date` on at least one workout. Dates are
calendar dates, independent of the running plan's informational timezone.
Scheduling may upload a missing template and then add the date in a separate
request. Calendar deduplication checks workout ID and date in the relevant
months. A local lock serializes uploader processes using the same Garmin token directory.
Writes from other machines, delayed visibility and partial failures can still
cause inconsistent results. Check Garmin Connect before retrying.

Workout uploads, scheduling and managed batch cleanup use the pinned `garminconnect` publishing adapter and its local saved-token directory. Activity sync and planning use Garmin's Personal API key in the ignored local file `private/garmin_personal_api_key` (mode `600`, in a mode `700` directory). Service changes, rate limits, or expired credentials can interrupt either connection. Keep both credential stores private, along with Codex credentials.
Use `--debug` for Codex failures. It saves CLI stderr beside the workout as
`<output>.debug.txt` instead of sending it to the terminal. Inspect it locally
before sharing. The Codex subprocess inherits only an allowlist of runtime
environment settings. It still runs under your OS account, so keep account
credentials outside directories available to an automated model process. Skip live upload if generation exits without a workout.

Offline tests use mocked account calls. The [roadmap](../ROADMAP.md) records
the live checks separately.

## Dependency verification

The full bootstrap installs the uploader dependencies and FIT decoder using a hash-locked wheel set on x86-64 Linux with CPython 3.12. Other platforms use pinned constraints and wheels. The `--reader-only` setup creates an isolated reader environment with the FIT decoder and does not install `garminconnect`. Hashes verify the
downloaded files against the repository lock. Dependency advisory checks
remain a separate step.

## Local multi-sport planning

Generation requires a Codex CLI whose `codex exec --help` lists
`--ignore-user-config`. Update Codex if the compatibility check fails.
The planner keeps this flag to isolate the request from user configuration.

Keep a named-profile JSON object on your machine. Each entry uses the same
fields as a single athlete profile, including an explicit `activity_type`.
Different names can use the same sport. For example:

```json
{
  "running": {
    "activity_type": "running",
    "goals": "Build endurance for a 10 km run",
    "availability": "30 minutes"
  },
  "cycling": {
    "activity_type": "cycling",
    "goals": "Prepare for a multi-day bikepacking trip of 60–80 km per day",
    "availability": "90 minutes",
    "equipment": "Outdoor cross bike"
  },
  "strength": {
    "activity_type": "strength_training",
    "goals": "Build full-body strength",
    "availability": "60 minutes",
    "equipment": "Fully equipped gym",
    "preferred_machines": ["Crunch machine"],
    "preferred_exercises": ["Cable-pull row"]
  }
}
```

Save it as `private/athlete_profiles.json`. From the repository root:

```bash
mkdir -p -m 700 private
activity_range=$(python -c 'from datetime import date, timedelta; d = date.today(); print(f"{d - timedelta(days=13)}..{d}")')
python download_activities.py --activity-type all --time-range "$activity_range" \
  --output private/recent_activities.json &&
python -m workoutplanner.chatgpt.week --activities private/recent_activities.json \
  --profiles private/athlete_profiles.json
```

Both ends of the 14-day lookback are included. The next-workout horizon is
today through six days ahead. Use `--lookback-days` to change the analysis
window and request a matching export. The prompt reserves the latest session for each profiled sport, then adds
other recent sessions as space allows. Counts report running, cycling, strength and a combined count for other
activity types in the window. The export may have gaps and raw chart samples stay local.

The planner uses one Codex request with a shared history and separate sport
goals. The resulting directory under `private/weekly/` contains one Garmin
plan per usable profile, plus `rationale.txt` with the priority, recovery
considerations and advice on spacing sessions if you choose more than one.
A profile can be deferred when recent information is insufficient. Use
`--prompt-only private/week_prompt.md` to inspect what would be sent before
making a model call.

Choose a plan and dry-run the corresponding JSON with the uploader. Upload
only the workouts you choose. After executing one, refresh the Garmin export
and generate again. The planner uses completed activities as history. Previous
suggestions do not count as completed workouts.

### Replace the previous Garmin batch

Add `--publish` to the local multi-sport generation command to upload every
profile's workout after validation. A deferred profile stops publication
before Garmin is changed. You can also publish an existing complete run:

```bash
python -m workoutplanner.garmin.publish private/weekly/RUN_DIRECTORY
```

WorkoutPlanner prefixes managed template names with a `[WP-…]` marker and
stores their Garmin IDs in `~/.garminconnect/workoutplanner-managed.json`.
Keep that file locally. Only templates recorded by this feature are eligible
for cleanup. The uploader verifies the stored signed name against Garmin
before deleting and does not infer ownership from old unmarked uploads.
The first publish establishes the tracked batch.

If a write fails, inspect Garmin Connect and retry the **same saved run**
with the publish command above. The journal records partial progress and the
next batch cannot replace an unfinished one. New templates are uploaded
before any old templates are retired. Publication creates workout templates.
It is separate from calendar scheduling.

### Offline workout validation

Run `python -S upload_workouts.py PLAN.json --dry-run` to validate a plan
with Python site packages disabled. WorkoutPlanner encodes running, cycling
and strength payloads locally. Its strength identifier mapping was checked
against all 1,527 entries in the pinned 0.3.20 catalog. Live publishing still
uses the Garmin client's JSON upload method and your existing local login.

### Scheduling a known Garmin template

When you have the workout ID from a successful upload, use
`python upload_workouts.py PLAN.json --schedule-existing ID YYYY-MM-DD`.
This mode checks the ID, name and sport, then schedules that specific template
once on the requested date. It never creates a template. It supports a
single-workout plan. The explicit date takes precedence over a plan date.
The original `--schedule` command can create a workout if the name lookup
finds no match. Use that mode when creation is intended.

### Live managed-batch acceptance

From the repository root, run
`PYTHONPATH=. .venv/bin/python tests/check_managed_batch.py`. This first
stage creates or reuses one unscheduled marked cycling test template, retries
the same saved batch and verifies its ID and name with Garmin. The check
uses the normal publisher lock and a separate local journal in the Garmin
token directory named `workoutplanner-acceptance.json`. Keep that journal
for the replacement test.

After stage A succeeds, pass `--replace-a` to the same check. This live
operation uploads unscheduled cycling test B and retires test A by its
verified ID and marker. It retries B, reads B back, and checks that Garmin
reports A missing. Run from the same account and local test journal. A
replacement receipt retains the old test ID for repeat verification.
