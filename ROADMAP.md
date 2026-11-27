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
generation, preview and live publication of one running, cycling and strength
workout in a single batch. Republishing that saved batch skipped duplicate
creation. Live replacement passed with isolated test templates. The project
runs locally.

## Activity context

Keep verified results, research and remaining constraints in the relevant
activity note. Keep personal history and athlete notes outside the repository.

- [Running](docs/activities/running.md)
- [Cycling](docs/activities/cycling.md)
- [Gym strength training](docs/activities/strength_training.md)
- [Bouldering](docs/activities/bouldering.md)

## Garmin integration status

The activity reader now uses WorkoutPlanner's Garmin Personal API client for
normal sync, without the `garminconnect` package. An isolated environment
containing only the FIT decoder passed live sync and multi-sport generation.
The legacy reader remains available for historical parity comparisons.

The `garminconnect` dependency is retained for live workout publishing,
scheduling and managed cleanup. Workout JSON encoding and exercise resolution
are implemented in WorkoutPlanner. Live uploads and managed replacement have
been verified for running, cycling and strength.

Garmin documents workout publishing in the Training API. Its overview
describes Training API access under Starter and Enterprise tiers, while its
dedicated page says Enterprise access only. Confirm program access and
workout operations with Garmin before replacing the publisher.

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

The athlete verified a 14-day Personal API sync, live sync in a FIT-only
environment, and generation for all three sports from Personal API history.
The running and cycling comparisons matched summary metrics and shared zone
durations on the sessions tested. See the activity notes for coverage gaps.

Live creation and duplicate detection passed for all three sports. Scheduling
by existing ID recognized the scheduled strength template on retry. In the
isolated replacement test, Garmin returned the replacement by ID and
confirmed the old template was absent. A separate three-workout planning
batch previewed three creations and zero retirements, published successfully,
and was recognized as already published on retry.

## Android application

The standalone native app is under `android/`; the Python local runner remains
available and unchanged. Profile editing and profile JSON import/export have
been tested on an Android phone. The app can store the Garmin Personal API key
encrypted with Android Keystore and preview recent activity summaries. Full
activity history and FIT metric sync, model generation and Garmin upload remain
open. The mobile milestones and provider access decisions are in
[`docs/android-app.md`](docs/android-app.md).
