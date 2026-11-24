# Gym strength training

Use `strength_training` as the planning target. The
[subskill](../../skills/workout-planner/subskills/strength_training.md) uses
the [strength research register](../../skills/workout-planner/references/strength_training-evidence.md)
to generate or adjust a manual gym session.

Use recent sets, reps, loads and units when Garmin provides them. Add exercise
history, available equipment and effort in athlete context when needed.
Exercise-level coverage and structured Garmin upload still need verification.

## Exercise-set sync

The pinned Garmin library exposes a read-only exercise-set endpoint. Strength
exports retain its available exercise data after the existing privacy filter.
The bounded prompt includes up to 12 set records per session, with nested
exercise names, rep counts and load units where returned. The athlete confirmed that a live Garmin export contained exercise sets.
