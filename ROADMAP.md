# WorkoutPlanner roadmap

## Completed local milestones

| Milestone | Status |
| --- | --- |
| Bootstrap and tests | The local setup and offline suite passed. |
| Activity sync | Filtered reads and strength exercise-set export are implemented. Live mixed-sport and strength exports were confirmed. |
| Planning input and research | Versioned input, three sport subskills, evidence registers and a local Garmin exercise catalog are in place. |
| ChatGPT handoff | Local prompt generation and authenticated Codex generation are available. Running, cycling and strength plans were reviewed locally. |
| Garmin acceptance | Running upload and duplicate detection passed. Cycling detected an existing generated ride. Strength upload, scheduling, and both duplicate checks passed. |

Live calendar deduplication was confirmed using a strength workout. The tests
cover common scheduling behavior across the uploader. Bouldering remains
export-only for the current scope.

## Local multi-sport planning

The on-demand planner uses a shared recent Garmin history to generate and
prioritize workout options for named profiles. The athlete verified live
generation and a Garmin dry-run. Managed batch replacement has offline
coverage and still needs live verification. The project runs locally and
has no GitHub-hosted workout workflow.

## Activity context

Keep verified results, research and remaining constraints in the relevant
activity note. Keep personal history and athlete notes outside the repository.

- [Running](docs/activities/running.md)
- [Cycling](docs/activities/cycling.md)
- [Gym strength training](docs/activities/strength_training.md)
- [Bouldering](docs/activities/bouldering.md)

## Replacing the Garmin client

1. Separate activity reads and workout publishing. The CLI now opens each
   client through its own factory in `workoutplanner/garmin/auth.py`. Both
   currently use the installed Garmin SDK and the existing local login.
2. Implement personal-key authentication for the desktop reader.
3. Compare activity exports from both readers for the same date range and
   switch once metric coverage is verified.
4. Workout encoding and strength exercise identifier resolution now run locally.
   Offline dry-runs for all three sports require only the Python standard library.
5. Verify supported publishing access, including scheduling and safe deletion.
6. Remove the SDK after a clean installation passes the complete workflow.

### Operations the replacement must cover

| Component | Required behavior |
| --- | --- |
| Activity reader | Page through recent activities, list by inclusive local dates, fetch a summary by ID, and filter completed activities by sport. |
| Optional detail | Export time series, splits, workout steps, heart-rate and power zones, weather and strength exercise sets. Keep missing sections explicit and preserve raw values and reported units. |
| Workout publisher | List owned workouts, create running, cycling or strength templates, look up a workout by ID, read the monthly calendar, schedule a workout and delete a verified managed template by ID. |
| Desktop credentials | The authentication module opens the local session. The reader and publisher receive authenticated clients. Login details do not belong in a workout or export. |

The CLI and planner continue to exchange the existing versioned JSON.
Synthetic [activity examples](tests/fixtures/garmin-activity-contract.json)
capture running splits, cycling power and strength loads for reuse by a
future Android client. The Python method names in
[the desktop interfaces](workoutplanner/garmin/contracts.py) describe the
current adapter. Android can implement the same data behavior in Kotlin.

Milestone 2 adds an opt-in Linux desktop login and single-activity probe.
Use the [Personal API check](docs/garmin-personal.md) to verify access on
your account. The normal sync and upload commands still use the SDK.

The athlete verified that the opt-in Personal API sync exported one activity
for a 14-day window. The next live check compares the compact planning fields
for one run and one ride against the default reader.

Live creation and duplicate detection have now passed for the local JSON
encoder on running, cycling and strength templates. The current live
transport still uses garminconnect. Scheduling by existing ID recognized the
scheduled strength template on retry. The isolated managed batch A retained its ID on retry
and its marked template was verified in Garmin. The isolated replacement
verified B by ID after retry and confirmed A was absent. The next live check
syncs a single activity with the Personal API in a FIT-only environment.
