# Running

Running is the default for export. Use `running` as the planning target and a
profile with a running goal. The exporter matches exact Garmin activity keys,
so select another key explicitly to export a running subtype. The prompt can
use mixed history and prioritizes recognized running types.

The [running subskill](../../skills/workout-planner/subskills/running.md) uses
the [evidence register](../../skills/workout-planner/references/running-evidence.md)
to generate a next session or adjust a named one. Recent duration, distance,
pace, heart rate, splits and athlete feedback help guide selection when
available. Zone labels require the athlete's settings to support numerical
targets.

The [output contract](../../skills/workout-planner/references/running-output.md)
covers timed steps, repeats and optional pace or heart-rate targets. Use
effort cues when the history cannot support a numeric target.

The athlete confirmed live generation, a run-walk dry-run, upload, and
duplicate upload detection. The live scheduling acceptance check used a
strength workout and the same calendar logic.

A [local reader comparison](../garmin-personal.md#compare-running-and-cycling-planning-inputs)
checks coverage of planning metrics for the same completed activity through
both Garmin clients. The live comparison matched 16 summary metrics for one session.
The legacy reader also supplied splits, heart-rate zones and power zones. The new FIT
path for those fields awaits a live comparison.
