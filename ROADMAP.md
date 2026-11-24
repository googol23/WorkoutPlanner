# WorkoutPlanner roadmap

## Completed local milestones

| Milestone | Status |
| --- | --- |
| Bootstrap and tests | The local setup and offline suite passed. |
| Activity sync | Filtered reads and strength exercise-set export are implemented. Live mixed-sport and strength exports were confirmed. |
| Planning input and research | Versioned input, three sport subskills, evidence registers and a local Garmin exercise catalog are in place. |
| ChatGPT handoff | Local prompt generation and authenticated Codex generation are available. Running, cycling and strength plans were reviewed locally. |
| Garmin acceptance | Running upload and duplicate detection passed. Cycling detected an existing generated ride. Strength upload, scheduling, and both duplicate checks passed. |

Live calendar deduplication was confirmed using a strength workout. The tests
cover common scheduling behavior across the uploader. Bouldering remains
export-only for the current scope.

## Next phase: GitHub Actions

1. Add credential-free CI for pushes and pull requests. Install the pinned
   dependencies, run the offline suite, and preview the synthetic plan.
2. Decide where a private live workflow should run and how it will authenticate
   to Garmin and Codex without exposing athlete files or credentials. Verify
   whether the chosen account sign-in works unattended on that runner.
3. Add a manually triggered generation workflow with profile and activity
   selection. Keep its first live check read-only on Garmin and review the
   plan before enabling writes.
4. Add reviewed upload and optional scheduling. Serialize live runs and verify
   retries against Garmin before considering a recurring trigger.

## Activity context

Keep verified results, research and remaining constraints in the relevant
activity note. Keep personal history and athlete notes outside the repository.

- [Running](docs/activities/running.md)
- [Cycling](docs/activities/cycling.md)
- [Gym strength training](docs/activities/strength_training.md)
- [Bouldering](docs/activities/bouldering.md)
