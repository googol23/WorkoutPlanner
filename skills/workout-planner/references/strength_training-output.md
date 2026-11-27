# Gym strength workout JSON output contract

Return one standalone JSON object with exactly `schema_version`, `sport`, and `workouts`. Keep rationale outside the object.

- `schema_version`: `"1.0"`; `sport`: `"strength_training"`.
- `workouts`: nonempty list. Each workout requires a unique nonempty `name`, positive integer `estimated_duration_seconds`, nonempty `warmup` cue, nonempty `exercises`, and optional `scheduled_date` (`YYYY-MM-DD`, only when requested and known).
- Each exercise has `name`, positive integer `sets`, `reps` with integer `min` and `max` (1 <= min <= max), nonnegative integer `rest_seconds`, and nonempty `effort` cue. Optional `load` is `{"value": positive number, "unit": "kg"}` or `"lb"`.
- Copy exercise names exactly from `garmin_exercise_catalog` in the input. Never invent an alias or machine name. Use `Hip Raise` for a floor glute bridge only if that exact catalog entry is supplied and suitable. If no safe, suitable catalog entry fits the available equipment, defer and ask a focused question.
- Estimate duration from warm-up, work, rests between sets, equipment changes, and setup. Do not count a rest after the final set. Keep the estimate within availability.