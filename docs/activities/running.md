# Running

- **Current support:** Completed running activities can be exported by recent count or activity ID. Structured workouts can be validated, uploaded and optionally scheduled.
- **Verification:** The offline suite and the uploader dry-run pass with the pinned Garmin dependency. A live mixed-sport export succeeded.
- **Next:** Verify an interactive ChatGPT response and a reviewed workout dry-run.
- **Evidence and decisions:** See the running skill and evidence register below.

## Filtered sync

Running remains the default type, including count and ID exports. Date ranges
select the exact `running` key by the recorded local date. Offline tests cover
the existing running commands.

## Planning input

Use `running` as the target. The history can supply distance, duration, pace
or speed, heart rate, zone time, splits, and workout steps when Garmin returns
them. The builder preserves exported values, units and sample descriptors.

A live mixed-sport export reported a completed-activity validation error after
login. The exporter now recognizes Garmin's detail `activityTypeDTO` shape
and uses the list entry's type when detail omits it. Both cases have offline
coverage.

## WorkoutPlanner skill

The [running skill](../../skills/workout-planner/subskills/running.md) supports generating
one next workout or adjusting a named session. It considers reported recovery
alongside recent training and distinguishes missing metrics from zero values.
The [evidence register](../../skills/workout-planner/references/running-evidence.md)
records the study populations, limitations, and planning implications.
The [output contract](../../skills/workout-planner/references/running-output.md)
keeps the rationale separate from Garmin-ready JSON.

A local live retry of the mixed-sport export succeeded after the activity type
fix. Upload and end-to-end ChatGPT generation still need live verification.

## ChatGPT handoff

The offline prompt builder bundles the running skill, evidence register and
uploader contract with a versioned planning input. Adjustment mode includes
only the named workout from the source plan. Review the generated prompt
before sharing it and dry-run the resulting workout JSON before uploading.

The authenticated generation command uses Codex signed in with ChatGPT and
validates the running plan before replacing the output file. Offline tests
cover response handling. A live generation from the athlete's account is
pending.
