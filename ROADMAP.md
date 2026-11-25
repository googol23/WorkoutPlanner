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

## Local multi-sport planning

The on-demand planner uses a shared recent Garmin history to generate and
prioritize workout options for named profiles. The athlete verified live
generation and a Garmin dry-run. Managed batch replacement has offline
coverage and still needs live verification. The project runs locally and
has no GitHub-hosted workout workflow.

## Activity context

Keep verified results, research and remaining constraints in the relevant
activity note. Keep personal history and athlete notes outside the repository.

- [Running](docs/activities/running.md)
- [Cycling](docs/activities/cycling.md)
- [Gym strength training](docs/activities/strength_training.md)
- [Bouldering](docs/activities/bouldering.md)
