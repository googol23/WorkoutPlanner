# Cycling subskill

Read the [cycling evidence register](../references/cycling-evidence.md).

- Compare recent cycling duration, power, heart rate, cadence, effort, terrain
  and indoor/outdoor conditions where available. Use comparable sessions and
  account for coasting and elevation when judging speed or power. A recent
  FTP in watts or an explicitly stated power zone range can anchor a target.
  Use perceived effort when a usable benchmark is missing.
- Choose the next ride's purpose from recent intensity and the athlete's goal.
  Give work duration, intensity and recovery together for intervals. Keep easy
  riding in the plan when appropriate and avoid importing a study protocol
  as the athlete's exact session. [C1, C2]

## Output

Return a standalone JSON object with `schema_version: "1.0"`,
`sport: "cycling"`, and a nonempty `workouts` array. Each workout has
a unique `name`, `total_duration_seconds`, and ordered `steps`. Each step
has `type` (`warmup`, `ride`, `recovery`, or `cooldown`),
`duration_seconds`, and an `effort` cue. Add `power_watts` as
`{"min": ..., "max": ...}` only if supported by the inputs. List repeated
steps explicitly and check that their sum matches the duration. This plan
is for manual use.
