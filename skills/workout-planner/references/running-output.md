# Running workout JSON output contract

Return exactly one standalone JSON object with these top-level fields: `schema_version`, `sport`, `timezone`, `units`, and `workouts`. Do not place rationale in the JSON.

- `schema_version`: `"1.0"`; `sport`: `"running"`.
- `timezone`: known IANA time zone. If unknown, use `"UTC"` for an unscheduled plan and state this assumption in the rationale.
- `units`: exactly `{"duration":"seconds","pace":"seconds_per_km","heart_rate":"bpm"}`.
- `workouts`: nonempty list. Each workout needs a unique nonempty `name`, positive integer `week` (use 1 for a single next workout), positive `total_duration_seconds`, and nonempty `steps`. Optional fields are `description` and `scheduled_date` (`YYYY-MM-DD`, only when requested and known). Use a distinct name for a revised workout if Garmin may already contain the previous name.

Timed step types are `warmup`, `run`, `interval`, `recovery`, and `cooldown`; each has positive `duration_seconds`. Optional `description` must be nonempty text. Omit a target when unsupported; otherwise use exactly one:
- `{"type":"none"}`
- `{"type":"pace","fast_seconds_per_km":360,"slow_seconds_per_km":400}` (example syntax only; fast must be <= slow)
- `{"type":"heart_rate","min_bpm":125,"max_bpm":140}` (example syntax only; whole BPM from 1 to 250 and min <= max)

A repeat step contains only `type: "repeat"`, integer `count` (2–100), and nonempty `steps`; avoid unnecessary nesting. The workout total must equal all timed steps plus each repeat group's expanded duration. Use no numeric targets unless supported by athlete-specific data.