# Cycling

- **Current support:** The exporter accepts Garmin activity type keys. Structured cycling upload is planned.
- **Next:** Verify Garmin cycling activity types and metric coverage. Verify support for uploading and scheduling structured cycling workouts before adding an adapter.
- **Evidence and decisions:** Record verified API behavior, reviewed sources and the planning rules they support as the cycling skill is developed.

## Filtered sync

The exporter accepts the exact `cycling` key. Subtypes can be selected by their
own Garmin key. Offline tests cover mixed-type results, inclusive local dates
and duplicate IDs. Garmin account behavior and cycling upload remain open.
