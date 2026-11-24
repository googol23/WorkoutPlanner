# WorkoutPlanner roadmap

## Baseline

WorkoutPlanner syncs completed Garmin activities and generates or adjusts
running, cycling, and gym strength workouts through ChatGPT-authenticated
Codex. Each supported sport has a research-backed subskill. The uploader
validates, previews, uploads, and optionally schedules the resulting plans.

Work through one milestone at a time. Keep each change in a focused Git commit
with a local verification command and record which checks need a Garmin account.

| Milestone | Scope | Acceptance |
| --- | --- | --- |
| 1. Reproducible local baseline | Restore the missing running plan test fixture with synthetic data and verify the pinned dependency installs. | A clean checkout passes the offline suite and previews a sample plan with `--dry-run`. |
| 2. Filtered activity sync | Add `--time-range` and `--activity-type` to the exporter. Define date boundaries, local time zone handling, Garmin activity type mappings, pagination and empty results. Preserve the existing running defaults and ID lookup. Use Garmin activity IDs to avoid duplicates in a sync result. | Mocked tests cover date boundaries, mixed activity types, multiple pages and legacy commands. A local Garmin run can compare exported IDs against Connect. |
| 3. Metrics and planning input | Inventory available per-activity Garmin metrics for running, cycling and indoor climbing, including bouldering where the activity metadata distinguishes it. Keep source values, units and timestamps where available. Record missing data and sampling limits. Add athlete goals, availability, recent feedback and preferences to a versioned planning input. | Representative sanitized fixtures validate the contract and cover sport-specific and missing metrics. |
| 4. Evidence-based WorkoutPlanner skill | Maintain a source list with DOI or URL, population, sport, evidence limitations and the planning rules each source informs. Define when to generate a new session, adjust an existing session or ask for missing input. Cover running, cycling and gym strength training through sport-specific subskills and evidence registers. | Sample sessions trace material training decisions to sources and input metrics and handle sparse data. |
| 5. ChatGPT handoff | Assemble the skill instructions, target activity type, goals, constraints, recent activity metrics, feedback and optional existing plan into a reviewable package for ChatGPT. Include a versioned output contract with a workout, rationale and source references. | Use sanitized data to generate a running workout in ChatGPT, validate its workout JSON and preview it with the uploader. Test generation and adjustment paths. |
| 6. Upload and local acceptance | Run the complete loop for running. Verify which structured workout types Garmin supports and extend upload adapters where supported. Document any manual handoff required for an unsupported workout type. Keep scheduling explicit. | Locally verify export, ChatGPT output, dry-run, upload and optional scheduling. Check duplicate behavior with approved account access. |

## Local acceptance status

Running upload and duplicate detection passed on a live account. Cycling's
live retry found the existing workout and skipped the duplicate. The athlete
reported that the strength workflow passed locally. Live calendar scheduling
and its duplicate check are the remaining acceptance checks.

## Activity context

Keep one Markdown document per activity type under `docs/activities/`.
Update the relevant document in each activity-specific commit with verified
Garmin behavior, sources, planning decisions, verification results and open
questions. Keep these records at the project level and exclude personal activity
data and athlete notes.

- [Running](docs/activities/running.md)
- [Cycling](docs/activities/cycling.md)
- [Bouldering](docs/activities/bouldering.md)
- [Gym strength training](docs/activities/strength_training.md)
