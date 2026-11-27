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
- Sign in through OpenAI's documented Sign in with ChatGPT plan-usage flow.
  Tokens are encrypted with Android Keystore. When the user taps Generate, the
  app sends the draft prompt to the public Responses API with `store: false`
  and streams the result back into a local review field. It never falls back
  to an API key or a separate API-billing project.

Time-series samples, weather and workout steps are not yet decoded. FIT
coverage depends on Garmin providing a downloadable file for the activity;
one missing or unsupported FIT file does not prevent summary sync. The returned
model text is not yet parsed into individually validated workouts, and Garmin
workout publishing is not implemented. The app does not read the desktop
Garmin tokens or Codex credentials.

ChatGPT plan usage is subject to the user's plan limits and OpenAI's eligibility
for this client. OpenAI documents the flow for open-source clients and selected
private apps; this repository is private, so account eligibility must be
confirmed by completing sign-in. A denial is shown in the app, and no API
billing fallback is attempted. The app sends the current profile/history
prompt to OpenAI only after the user taps Generate. `store: false` prevents
Responses API response storage; it does not make the request local.

During sign-in, the app opens the system browser and waits for OpenAI to return
to a loopback callback on the same phone. The browser shows a confirmation page;
then return to WorkoutPlanner while it exchanges and validates the tokens. The
Plan screen shows which stage is active and times out with a retry message if
the callback does not arrive.

Android uses Garmin's official
[`fit-java-sdk`](https://github.com/garmin/fit-java-sdk), pinned to
`com.garmin:fit:21.222.0`. Garmin distributes this library under the
[FIT Protocol License](https://github.com/garmin/fit-java-sdk/blob/main/LICENSE.txt).

## Integration sequence

1. **Confirm provider access.** Garmin's Personal API is the read path.
   Garmin's Training API is the approved workout-publishing path and requires
   Enterprise access. For generation, this app uses OpenAI's documented
   Sign in with ChatGPT plan-usage flow for public clients. The user must grant
   both `resource.invoke` and `chatgpt.tokens.use.direct`; OpenAI may reject
   private clients that are not enabled for the feature.
2. **Finish Garmin read-only sync.** Compare FIT-derived Android output with
   the desktop reader for running, cycling and strength fixtures, then add
   time-series and other useful fields only where Garmin provides a stable
   source. Summary/detail and FIT lap/zone/set extraction are implemented;
   live parity and coverage remain to be checked on the phone.
3. **Finish workout response review.** ChatGPT sign-in and one-shot generation
   are implemented. Parse and validate one typed workout per profile against
   the shared Garmin contract, show the rationale and plans separately, and
   allow selection before any publishing action.
4. **Add publishing.** Use Garmin's approved Training API if available. Keep
   publishing separate from activity reading, verify returned workout IDs and
   make retries idempotent. Scheduling remains a separate explicit action.
5. **Check parity and recovery.** Compare Android output against the local
   Python workflow using shared fixtures, then test network loss, expired
   credentials, partial uploads and repeated runs.

## Security model

The intended design has no WorkoutPlanner backend: profile data, activity
history, and credentials stay in app-private storage on the phone. The Garmin
key is AES-GCM encrypted with a key held by Android Keystore, excluded from
backup, and removable from the app. ChatGPT OAuth tokens are also encrypted
with an Android Keystore key and removable by disconnecting. The app requests
only the scopes needed for plan usage, verifies the ID-token signature and
claims, stores the verified subject/email with access and refresh tokens, and
does not persist the ID token or expose tokens to the UI. Disconnect removes
credentials from the phone; remote app access can also be managed in ChatGPT
settings. Direct requests send synced activity details and profile data to
Garmin and, only after tapping Generate, to OpenAI.

The profile JSON is user data, not a credential. The first milestone stores it
in app-private storage and supports document-picker export/import. Exported
files are controlled by the user and may be visible to other apps or cloud
storage selected in the document picker.

## Build

Install Android Studio with its Android SDK and JDK. Open the `android/`
directory as a separate Gradle project. The root Python bootstrap does not
install Android build tools and remains unchanged.
