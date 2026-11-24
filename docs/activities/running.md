# Running

- **Current support:** Completed running activities can be exported by recent count or activity ID. Structured workouts can be validated, uploaded and optionally scheduled.
- **Verification:** The offline suite and the uploader dry-run pass with the pinned Garmin dependency. Live account behavior remains unverified.
- **Next:** Define date filtering and verify Garmin's running activity type mappings. Record available metrics, units and missing fields before adding planning rules.
- **Evidence and decisions:** Add reviewed training sources and the planning rules they support as the running skill is developed.

## Filtered sync

Running remains the default type, including count and ID exports. Date ranges
select the exact `running` key by the recorded local date. Offline tests cover
the existing running commands. Garmin account behavior is pending a live check.

## Planning input

Use `running` as the target. The history can supply distance, duration, pace
or speed, heart rate, zone time, splits, and workout steps when Garmin returns
them. The builder preserves exported values, units and sample descriptors.
