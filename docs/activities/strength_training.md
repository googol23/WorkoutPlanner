# Gym strength training

Use `strength_training` as the planning target. The
[subskill](../../skills/workout-planner/subskills/strength_training.md) uses
the [strength research register](../../skills/workout-planner/references/strength_training-evidence.md)
to generate or adjust a structured gym session.

Use recent sets, reps, loads and units when Garmin provides them. Add exercise
history, available equipment and effort in athlete context when needed.
Live structured Garmin upload still needs verification.

## Exercise-set sync

The pinned Garmin library exposes a read-only exercise-set endpoint. Strength
exports retain its available exercise data after the existing privacy filter.
The bounded prompt includes up to 12 set records per session, with nested
exercise names, rep counts and load units where returned. The athlete confirmed that a live Garmin export contained exercise sets.

## Upload acceptance

The adapter uses the pinned Garmin catalog and typed strength workout model.
It converts sets, rep targets, timed rest, and optional loads. Offline tests
cover conversion, unknown exercise rejection, and duplicate-name handling.
Live strength upload remains to be checked.

A live generation produced a plan with the common name “Glute Bridge.”
The adapter now resolves it to Garmin's “Hip Raise” entry and suggests catalog
matches for other unknown names. Suggestions require manual selection.
