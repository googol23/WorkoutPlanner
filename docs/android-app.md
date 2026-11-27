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
  key, removal, and an on-demand connection check.
- A temporary preview of up to 20 completed activity summaries from the last
  14 days. Summary rows stay in memory and are not yet saved as planning input.

The preview is only a connection check. Full activity detail, FIT metrics,
local activity-history persistence, OpenAI generation and Garmin workout
publishing are not implemented. The app does not read the desktop Garmin tokens
or Codex credentials.

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
2. **Finish Garmin read-only sync.** Fetch full activity summaries and details
   for the selected window, download and parse original FIT records, preserve
   the established activity JSON contract, and save it in app-private storage.
   The current connection check only previews summaries.
3. **Add prompt construction and generation.** Port the compact multi-sport
   input rules and schema validation. Present the exact activity data to be
   sent for generation. Keep model credentials on-device and use only an
   officially supported authorization path.
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
