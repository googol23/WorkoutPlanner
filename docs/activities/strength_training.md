# Gym strength training

Use `strength_training` as the planning target. The
[subskill](../../skills/workout-planner/subskills/strength_training.md) uses
the [strength research register](../../skills/workout-planner/references/strength_training-evidence.md)
to generate or adjust a structured gym session.

Use recent sets, reps, loads and units when Garmin provides them. Add exercise
history, available equipment and effort in athlete context when needed.

## Exercise-set sync

The pinned Garmin library exposes a read-only exercise-set endpoint. Strength
exports retain its available exercise data after the existing privacy filter.
The bounded prompt includes up to 12 set records per session, with nested
exercise names, rep counts and load units where returned. The athlete confirmed that a live Garmin export contained exercise sets.

## Upload acceptance

The adapter uses the local Garmin exercise catalog and JSON workout encoder.
It converts sets, rep targets, timed rest, and optional loads. Offline tests
cover conversion, unknown exercise rejection, and duplicate-name handling.
The athlete reported that the local generation, dry-run and upload workflow
passed. A dated strength workout was uploaded and scheduled in Garmin
Connect. A second invocation reported both `Already uploaded` and
`Already scheduled` for the same workout and date.

A live generation produced a plan with the common name “Glute Bridge.”
The adapter now resolves it to Garmin's “Hip Raise” entry and suggests catalog
matches for other unknown names. Suggestions require manual selection.

## Local exercise catalog

The repository ships the [complete exercise catalog](../../skills/workout-planner/references/garmin-strength-exercises.json)
from `garminconnect==0.3.20` with 1,527 exact names grouped by Garmin category.
Tests compare the local names with the pinned library. The strength prompt
includes a default selection plus matches for preferred exercises, preferred
machine names and exercises already in a workout being adjusted. The full
catalog stays local.

## Athlete profile

Use `athlete_strength.json` with a matching target, your actual equipment,
and optional exercise or machine preferences:

```json
{
  "activity_type": "strength_training",
  "goals": "Build general strength",
  "availability": "30 minutes",
  "equipment": "Leg press, cable station, dumbbells and a bench. No squat rack.",
  "preferred_machines": ["Leg Press", "Lat Pull-down"],
  "preferred_exercises": ["Dumbbell Bench Press", "Goblet Squat"]
}
```

Machine matches are name-based candidates. Review the plan for equipment fit
and review any proposed load. Garmin receives the lower rep target, with the
full range in the step note. The warmup is a workout note.

```bash
python build_planning_input.py --activities strength_activities.json \
  --athlete athlete_strength.json --activity-type strength_training > strength_input.json &&
python generate_next_workout.py --planning-input strength_input.json --output next_strength.json &&
python upload_workouts.py next_strength.json --dry-run
```

The desktop Personal API probe retrieved a known completed strength activity
using the athlete's key. The first comparison could not establish exercise-set
coverage. The probe now reports counts separately for the existing export,
activity detail and, if needed, associated workouts. Associated workout data
alone does not establish that the recorded sets, reps and loads are equivalent.

A live comparison found 36 exercise-set records in the existing export and no
exerciseSets list in either Personal API JSON response for that session.

Live FIT verification for one session found all 36 set records, including
18 active sets with matching repetitions in returned order. All 18 active
sets had a recorded FIT weight in kg and none had an exercise subtype.
Equivalence with the legacy loads was unverified. The opt-in Personal API
sync now exports those recorded FIT fields for planning.

The [strength encoder check](../../tests/fixtures/strength-encoder-check.json)
uses two sets of eight Goblet Squats at 10 kg with one 60-second rest between
sets. Submit the unscheduled plan twice to verify upload and duplicate
detection, then inspect the exercise, repetitions, load and rest in Connect.

Garmin Connect created the strength template from the local JSON encoder.
A second submission found the same ID and skipped creation. The upload
receipt verifies creation and deduplication. The displayed exercise, reps,
weight and rest remain to be checked in Connect.
