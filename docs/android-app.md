# Android app

## Purpose and boundary

The Android app is a native Kotlin application that will let the user maintain
named profiles for running, cycling and strength, sync recent Garmin activity,
generate one workout option per profile, review the priority rationale and
choose which options to upload.

The Python CLI remains a supported local runner. The Android project is isolated
under `android/`; it does not import Python modules, run Codex CLI, or alter the
existing local credentials and workflow. Both clients use the same versioned
JSON profile and workout contracts. This allows the local runner to remain
usable if mobile development or a remote service integration is unavailable.

## Current implementation

The initial Android milestone provides:

- Native profile creation and editing for running, cycling and strength.
- Validation for the named-profile JSON format accepted by
  `workoutplanner.chatgpt.week`.
- Import and export through Android's document picker.
- App-private profile storage. Profiles are not written to the repository or
  uploaded by this milestone.
- Garmin Personal API key entry, AES-GCM encryption using an Android Keystore
  key, removal, and on-demand sync.
- Read-only sync of completed activity summaries and details over the last 14
  days, paginated with a 100-activity safety limit. The JSON is saved in
  app-private storage using the existing schema version 1.0.
- Download and decode the original FIT activity file when Garmin makes it
  available. The sync extracts lap summaries, time in heart-rate and power
  zones, and recorded strength set data. Unsupported or unavailable FIT data
  stays explicitly listed under `unavailable_fields`.
- Build a compact local planning preview from every saved profile and the
  available cross-sport history from the last 14 days. The app displays both
  the structured input and the draft instruction without sending either to a
  model or other service.

Time-series samples, weather and workout steps are not yet decoded. FIT
coverage depends on Garmin providing a downloadable file for the activity;
one missing or unsupported FIT file does not prevent summary sync. OpenAI
generation and Garmin workout publishing are not implemented. The app does
not read the desktop Garmin tokens or Codex credentials.

Android uses Garmin's official
[`fit-java-sdk`](https://github.com/garmin/fit-java-sdk), pinned to
`com.garmin:fit:21.222.0`. Garmin distributes this library under the
[FIT Protocol License](https://github.com/garmin/fit-java-sdk/blob/main/LICENSE.txt).

## Integration sequence

1. **Confirm provider access.** Garmin's Personal API is the supported path for
   reading an individual's own activity data. Garmin's Training API is the
   supported workout publishing path and requires Enterprise access. If that
   access is unavailable, publishing from Android would require a separate
   decision about maintaining the project's unofficial personal uploader.
   OpenAI's consumer ChatGPT sign-in is not a general-purpose authorization
   flow for arbitrary apps. Confirm an eligible ChatGPT integration before
   promising account-based generation; the OpenAI API key route has separate
   API billing.
2. **Finish Garmin read-only sync.** Compare FIT-derived Android output with
   the desktop reader for running, cycling and strength fixtures, then add
   time-series and other useful fields only where Garmin provides a stable
   source. Summary/detail and FIT lap/zone/set extraction are implemented;
   live parity and coverage remain to be checked on the phone.
3. **Connect supported model generation.** Prompt preview is implemented
   locally. Select an officially supported Android authorization path before
   enabling transmission to a model provider.
4. **Add workout review.** Show the rationale and one plan for every configured
   profile. Let the user select one or several plans before upload; generation
   alone must not publish or schedule anything.
5. **Add publishing.** Use Garmin's approved Training API if available. Keep
   publishing separate from activity reading, verify returned workout IDs and
   make retries idempotent. Scheduling remains a separate explicit action.
6. **Check parity and recovery.** Compare Android output against the local
   Python workflow using shared fixtures, then test network loss, expired
   credentials, partial uploads and repeated runs.

## Security model

The intended design has no WorkoutPlanner backend: profile data, activity
history, and credentials stay in app-private storage on the phone. The Garmin
key is AES-GCM encrypted with a key held by Android Keystore, excluded from
backup, and removable from the app. The access token is held only for the
request and not persisted. Direct provider requests still send the relevant
data to Garmin or OpenAI. The app must show that data boundary before
generation.

The profile JSON is user data, not a credential. The first milestone stores it
in app-private storage and supports document-picker export/import. Exported
files are controlled by the user and may be visible to other apps or cloud
storage selected in the document picker.

## Build

Install Android Studio with its Android SDK and JDK. Open the `android/`
directory as a separate Gradle project. The root Python bootstrap does not
install Android build tools and remains unchanged.
