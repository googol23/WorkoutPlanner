---
name: running-workout-planner
description: Plan or adjust one Garmin-ready running workout using the runner's goals, recent running, cross-training load, recovery feedback, and running research.
---

# Running workout planner

Use this skill for a profile whose activity type is `running`. Produce one next run option that serves the profile goal and fits its stated time and constraints. For multi-profile planning, coordinate with the WorkoutPlanner root skill and consider all other sports as context.

## Review the runner's evidence

- Confirm the history dates, export window, and number of reported activities. Separate running sessions from cycling, strength, walking, and unknown types. A missing run in a partial export does not establish that the runner rested.
- For comparable runs, review frequency and duration first, then distance, pace/speed, heart rate, elevation, splits, intervals, aerobic/anaerobic training effect, and subjective feedback where present. Distinguish moving time from elapsed time. Consider surface, hills, weather, indoor/treadmill mode, and GPS quality before comparing pace.
- Use the athlete's actual running heart-rate zones and zone basis when supplied. Zone labels alone do not justify numeric BPM targets. Do not estimate threshold pace or max HR from one activity's average or peak.
- Treat Garmin device load and training-effect fields as device estimates; retain their names and units and do not equate them with a complete physiological load measure.

## Select and dose the next run

1. **Check readiness.** Give recent pain, fatigue, illness, sleep/stress notes, and hard sessions across all sports appropriate weight. If there is pain that changes gait or worsens while running, defer the run and ask about symptoms or suggest professional assessment as appropriate. Do not diagnose.
2. **Choose one purpose.** Match the goal and recent pattern: easy aerobic running, longer easy running, run-walk, controlled tempo/threshold work, short intervals, hills, or a recovery-oriented session. Avoid a second hard session when recent running or strength/cycling load suggests incomplete recovery. Do not add intensity just because the history contains enough data to calculate a target.
3. **Set a defensible dose.** Anchor duration to time availability and a recently tolerated comparable run, adjusted for feedback and other training. For sparse history, choose a conservative easy/run-walk session and use talk-test or perceived-effort cues. Avoid fixed percentage progressions and universal weekly intensity ratios. Increase only a small number of session demands at once.
4. **Specify intensity.** Use pace or heart-rate targets only when the profile or comparable, recent, sport-specific data supports them. Prefer effort cues when data are stale, conditions differ, or zone settings are unknown. Keep easy work genuinely conversational. For intervals, state work duration and intensity plus recovery duration and effort.
5. **Build and check the session.** Include a practical warm-up and cool-down when appropriate. Use repeat groups for repeated work/recovery; calculate repeats into the total. Stay inside the time budget, including warm-up and cool-down. Do not prescribe a schedule date unless requested.

## Research use

Read the [running evidence register](../../references/running-evidence.md). R1 supports keeping easy work in the broader training picture, not imposing a quota on one athlete. R2 and R3 support combining workload trends with athlete response and self-report. R4 cautions against universal running-load progression rules. G1 is Garmin device guidance: use actual configured zones, not assumed zone labels. Cite only the IDs that materially support the choice, with links in the rationale.

## Return contract

Read and follow the [running JSON output contract](../../references/running-output.md). Return one standalone `schema_version: "1.0"`, `sport: "running"` object. Keep rationale outside the JSON. The JSON is consumed by WorkoutPlanner's validator and Garmin encoder; do not add unsupported fields, prose, or upload claims.