# Cycling

Use `cycling` as the planning target and tag the athlete profile with
`"activity_type": "cycling"`. Supply a cycling goal or state how the ride
should support another sport. Add riding background, available equipment and
a recent power benchmark when relevant.

The exporter accepts the exact Garmin type key `cycling`. Select subtypes
by their own keys or export mixed history. The prompt prioritizes recognized
rides and uses other sports as recovery context. Power, cadence and zone data
depend on the recording. Use effort cues when no defensible watt target is
available.

The [cycling subskill](../../skills/workout-planner/subskills/cycling.md) and
[research register](../../skills/workout-planner/references/cycling-evidence.md)
guide generation and adjustments. Garmin conversion supports timed steps and
optional power ranges. Calendar placement uses the shared uploader.

The athlete confirmed a generated endurance ride passed preview and a live
retry found the existing ride and skipped upload. The live scheduling
acceptance check used a strength workout.

A [local reader comparison](../garmin-personal.md#compare-running-and-cycling-planning-inputs)
checks coverage of planning metrics for the same completed activity through
both Garmin clients. The live comparison matched 12 summary metrics for one session.
Both readers returned six planner split rows. The FIT path returned six
heart-rate zone rows, versus five from the legacy reader.
Moving time and legacy zone lower bounds still need verification.
