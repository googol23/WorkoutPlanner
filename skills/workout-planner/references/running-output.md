# Running workout output

Return the rationale separately. In the workout JSON use exactly these
top-level fields:

- `schema_version` is `"1.0"`.
- `sport` is `"running"`.
- `timezone` is a known IANA zone. If unknown, use `"UTC"` for an unscheduled
  plan and state the assumption in the rationale.
- `units` is `{"duration":"seconds","pace":"seconds_per_km","heart_rate":"bpm"}`.
- `workouts` is a nonempty list. Each workout needs a unique `name`, positive
  integer `week` (use 1 for a standalone workout), `total_duration_seconds`,
  and nonempty `steps`. Optional fields are `description` and
  `scheduled_date` in YYYY-MM-DD format. Include a date only when requested
  and known. Name revised workouts distinctly if the original might already
  exist in Garmin because the uploader skips an existing name.

Timed steps use a `type` of `warmup`, `run`, `interval`, `recovery`, or
`cooldown`, and positive `duration_seconds`. Steps can include a nonempty
`description` and a `target` using one of the following forms:

- `{"type":"none"}` or omit the target for an untargeted step.
- `{"type":"pace","fast_seconds_per_km":360,"slow_seconds_per_km":400}`, with
  positive values and fast less than or equal to slow.
- `{"type":"heart_rate","min_bpm":125,"max_bpm":140}`, with increasing whole
  numbers from 1 to 250. The pace and heart-rate numbers above illustrate
  syntax and are not athlete targets.

Repeat steps contain only `type: "repeat"`, an integer `count` from 2 to 100,
and nonempty `steps`. Avoid unnecessary nesting. Add the timed step durations
and multiply each repeat group by its count to get the declared total.

Ask the athlete to save the JSON as `next_workout.json` and verify it with
`python upload_workouts.py next_workout.json --dry-run`.
