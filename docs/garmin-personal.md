# Check a Garmin Personal API key on Linux

Use a logged-in desktop session with an unlocked Secret Service keyring.
Bootstrap installs `libsecret-tools` on Debian and Ubuntu. For an existing
installation run `sudo apt-get install libsecret-tools`.

1. Sign in to Garmin Connect Web and follow [Garmin's Personal API key instructions](https://developer.garmin.com/gc-developer-program/personal/personal-api/).
   Choose an expiration and copy the key when Garmin displays it.
2. From the project directory run the command below and enter the key at the hidden prompt.

   ```bash
   .venv/bin/python -m workoutplanner.garmin.personal login
   ```

3. Open a completed strength activity in Garmin Connect Web. Copy the numeric
   activity ID from the address bar. To read it and compare against the
   existing exporter, run these commands in the same shell.

   ```bash
   read -rp 'Garmin strength activity ID: ' activity_id
   mkdir -p -m 700 private &&
   .venv/bin/python download_activities.py --activity-id "$activity_id" \
     --activity-type strength_training --output private/strength-reference.json &&
   .venv/bin/python -m workoutplanner.garmin.personal check "$activity_id" \
     --compare-export private/strength-reference.json
   ```

The check also works without the comparison file. A successful read proves
account access. The check reports separately whether the activity detail
response includes matching exercise-set records. Missing sets mean that
coverage still needs investigation when migrating the downloader.

The client sends credentials directly to Garmin over HTTPS. It exchanges the
stored key for an in-memory access token each time the check runs. Repeat
`login` to replace the stored key after rotation. Revoke the key in Garmin
Connect Web to disable it. The existing workout publisher uses its original
local login.

The protocol reference is [Garmin's official Python example](https://github.com/garmin/connect-personal-api-python).
WorkoutPlanner implements just the token exchange and activity-detail GET
directly. Garmin's example also documents searching activities, reading
workouts associated with an activity, and downloading the original activity
file. The workout lookup reads a completed activity's data. Creating a
planned workout is a separate publishing operation.

To repeat the comparison, reuse the saved reference file and run only the
`personal check` command. It reports missing or empty exercise-set lists by
source, and consults the associated-workouts endpoint when the activity detail
has no sets. A zero count describes the returned data, not how many sets you did.
