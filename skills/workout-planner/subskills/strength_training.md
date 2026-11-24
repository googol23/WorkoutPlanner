# Gym strength training subskill

Read the [strength training evidence register](../references/strength_training-evidence.md).

- Review recent exercise-level sets, reps, loads and units, equipment,
  experience, effort or reps in reserve, soreness and recent feedback.
  Garmin session duration and heart rate can describe session context.
  Ask for exercise history or use a conservative effort cue if it is missing.
- Match exercises to the movement goals, available equipment and experience.
  Set a practical work-set count, rep range, rest and effort goal. Consider
  heavier loading for strength when experience and prior work support it.
  For hypertrophy, consider the broader training volume and recovery. Adapt
  one variable at a time when the recent session supports progression. [S1, S2]
- Use submaximal effort when suitable. Avoid requiring failure or assuming
  a one-repetition maximum from missing logs. Give a substitution if
  equipment is unavailable and a specific exercise is essential. [S1, S3]

## Output

Return a standalone JSON object with `schema_version: "1.0"`,
`sport: "strength_training"`, and a nonempty `workouts` array. Each workout
has a unique `name`, `estimated_duration_seconds`, a `warmup` cue and
an ordered `exercises` array. Use exact Garmin exercise display names. Verified
examples include Goblet Squat, Dumbbell Lunge, Leg Press, Dumbbell Bench Press,
Barbell Bench Press, Push-up, Dumbbell Row, Seated Cable Row, Dumbbell Shoulder
Press and Dumbbell Biceps Curl. Favor a matching catalog exercise the athlete
can perform with their equipment. Each exercise has a `name`, positive whole
`sets`, a `reps` object with whole `min` and `max`, `rest_seconds`,
and an `effort` cue. Include optional `load: {"value": ..., "unit": "kg"}`
(or `"lb"`) only when the input supports it. Account for warmup, work,
rest, and setup when estimating duration. The uploader uses the lower end
of the rep range as the watch target and preserves the range in the step
note. It inserts rest between sets and keeps the warmup as a workout note.
Use an explicit `scheduled_date` only when requested and known. Preview the
result with the Garmin uploader's `--dry-run`.
