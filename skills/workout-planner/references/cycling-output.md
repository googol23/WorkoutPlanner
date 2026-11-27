# Cycling workout JSON output contract

Return one standalone JSON object with exactly `schema_version`, `sport`, and `workouts`. Do not include rationale inside the object.

- `schema_version`: `"1.0"`; `sport`: `"cycling"`.
- `workouts`: nonempty list. Each workout has a unique nonempty `name`, positive integer `total_duration_seconds`, nonempty ordered `steps`, and optional `scheduled_date` in `YYYY-MM-DD` only when requested and known.
- Each step has `type` (`warmup`, `ride`, `recovery`, or `cooldown`), positive integer `duration_seconds`, and nonempty `effort` cue.
- Optional `power_watts` is exactly `{"min": number, "max": number}`, with positive values and min <= max. Add it only when a credible current cycling benchmark supports the target.
- Expand all repeated efforts into explicit ordered steps. The sum of step durations must equal the workout total and stay within the profile's available time.
- Do not add cadence, heart-rate, distance, title metadata, or other fields unsupported by the Garmin encoder contract.