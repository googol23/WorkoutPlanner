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

### Compare the original strength activity

Use the same activity ID and saved reference export. The optional diagnostic
uses Garmin's FIT decoder locally and reads one FIT member from the original
ZIP in memory. Run from the project root with your numeric ID in place of ID.

```bash
(
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY http_proxy https_proxy all_proxy ftp_proxy
  .venv/bin/python -m pip install -r setup/requirements-fit-check.txt &&
  .venv/bin/python -m workoutplanner.garmin.personal check-fit ID --compare-export private/strength-reference.json
)
```

The report separates rest and active records and compares repetitions in
returned order. It only compares loads when both sides have explicit,
comparable units. Device recordings and subsequent Garmin Connect edits can
differ. The optional decoder is independent of Garmin login and workout uploads.

### Opt-in activity sync

Pass `--source personal` to `download_activities.py` with the existing
`--activity-id`, `--limit` or inclusive `--time-range` options. Use a
separate output file while comparing the readers. Install the FIT decoder
as above for strength, running and cycling history. The desktop CLI still uses the project environment.
The Personal API supplies summaries across sports. For strength it also
reads recorded sets from the original FIT with loads in kilograms. No
exercise name is inferred from reps, load or a broad exercise category.
Running and cycling exports read recorded laps and session heart-rate and power
zone durations from the original FIT. Availability depends on the device file.
Multisession files are skipped for these fields. Zone boundaries, detailed
samples, weather and workout steps still require the default reader.
The personal export uses the existing JSON format accepted by the local planner.

### Compare running and cycling planning inputs

Run `.venv/bin/python -m workoutplanner.garmin.compare_endurance` with both
local Garmin logins configured. The check finds a recent completed run and
ride using the Personal API sport searches, including supported subtypes,
without the planner's 14-day cutoff. It reads each selected activity ID with
both clients and compares the compact fields that reach the planner. It
prints counts and field names. Equality applies to the selected sessions
and the planner's bounded summaries, including its first splits and zones.

For differing sections the check aligns splits by order and zones by number.
Each field shows counts of exact matches, differing values and one-sided
fields among aligned rows. Extra zone numbers are listed separately. Running
lap cadence uses steps per minute, including fractional strides when recorded.
Moving duration requires an explicit FIT moving-time field.

For lap speeds, the comparison also prints the largest absolute difference
in m/s over aligned numeric pairs. Extra zones are counted separately by
positive, zero and unknown duration. These diagnostics preserve exact
comparison and leave recorded values intact.

### Standalone reader environment

The Personal API downloader can run in a separate Python 3.12+ environment
with only the pinned FIT decoder. From the repository root:

```bash
(
  set -e
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY FTP_PROXY http_proxy https_proxy all_proxy ftp_proxy
  mkdir -p -m 700 private
  .venv/bin/python -m venv private/reader-venv
  py=private/reader-venv/bin/python
  "$py" -m pip --isolated install -r setup/requirements-fit-check.txt
  "$py" -c 'from importlib.util import find_spec; assert find_spec("garminconnect") is None'
  "$py" download_activities.py --source personal --activity-type all --limit 1 \
    --output private/standalone-reader.json
)
```

Use the desktop session containing your existing Garmin Personal API key.
Live publishing and the legacy reader still use the main project environment.
