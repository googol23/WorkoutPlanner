# Cycling

- **Current support:** The exporter accepts Garmin activity type keys. The uploader accepts structured cycling workouts.
- **Next:** Verify Garmin cycling activity types and metric coverage. Verify support for uploading and scheduling structured cycling workouts before adding an adapter.
- **Evidence and decisions:** Record verified API behavior, reviewed sources and the planning rules they support as the cycling skill is developed.

## Filtered sync

The exporter accepts the exact `cycling` key. Subtypes can be selected by their
own Garmin key. Offline tests cover mixed-type results, inclusive local dates
and duplicate IDs. Live cycling upload still needs verification.

## Planning input

Use `cycling` as the target. The builder retains power, power zones, cadence,
speed and heart-rate metrics where they appear in the export. Power and cadence
coverage depends on what the activity recorded and what Garmin returned.

## WorkoutPlanner subskill

The [cycling subskill](../../skills/workout-planner/subskills/cycling.md) uses
the [cycling research register](../../skills/workout-planner/references/cycling-evidence.md)
to generate or revise a structured ride. It uses recent comparable ride data and
athlete feedback, with effort cues when power targets are unsupported.

## Upload acceptance

The pinned Garmin library provides a typed cycling workout and custom power
targets. Offline tests cover step conversion, dispatch and duplicate-name
handling. Preview a generated cycling workout before the first live upload.

## Athlete context

Use a cycling profile tagged `activity_type: "cycling"` with a cycling goal
or an explicit cross-training purpose. The prompt uses rides for cycling
benchmarks and keeps other sports as recovery context. A local input review
found a running goal paired with a cycling target. The builder now rejects
an untagged or differently tagged profile for cycling.
