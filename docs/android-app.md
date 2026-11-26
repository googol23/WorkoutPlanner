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

The app currently has no Garmin or OpenAI connection and does not publish
workouts. It does not require or read the desktop Garmin tokens or Codex
credentials.

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
2. **Add profile persistence and migration.** Provide explicit versioned
   import/export and keep profile fields compatible with the Python runner.
3. **Add Garmin read-only sync.** Implement the Personal API key flow, token
   exchange, activity history window and FIT parsing in a native Android data
   module. Store secrets with Android Keystore-backed encryption. Keep a
   visible sync status and allow credentials and local activity history to be
   removed.
4. **Add prompt construction and generation.** Port the compact multi-sport
   input rules and schema validation. Present the exact activity data to be
   sent for generation. Keep model credentials on-device and use only an
   officially supported authorization path.
5. **Add workout review.** Show the rationale and one plan for every configured
   profile. Let the user select one or several plans before upload; generation
   alone must not publish or schedule anything.
6. **Add publishing.** Use Garmin's approved Training API if available. Keep
   publishing separate from activity reading, verify returned workout IDs and
   make retries idempotent. Scheduling remains a separate explicit action.
7. **Check parity and recovery.** Compare Android output against the local
   Python workflow using shared fixtures, then test network loss, expired
   credentials, partial uploads and repeated runs.

## Security model

The intended design has no WorkoutPlanner backend: profile data, activity
history, and credentials stay in app-private storage on the phone. Credentials
must be encrypted using Android Keystore-backed keys, excluded from backup, and
removable from the app. Direct provider requests still send the relevant data
to Garmin or OpenAI. The app must show that data boundary before generation.

The profile JSON is user data, not a credential. The first milestone stores it
in app-private storage and supports document-picker export/import. Exported
files are controlled by the user and may be visible to other apps or cloud
storage selected in the document picker.

## Build

Install Android Studio with its Android SDK and JDK. Open the `android/`
directory as a separate Gradle project. The root Python bootstrap does not
install Android build tools and remains unchanged.
