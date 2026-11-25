# Weekly Garmin workout

The workflow runs Sundays at 08:17 Europe/Berlin. It reads up to 20 recent
Garmin activities, generates one workout for the local profile through Codex,
validates it offline, then uploads the workout template. It leaves Garmin
calendar placement to a separate command.

## Runner setup

1. Make the repository private. Register a dedicated Linux self-hosted runner
   with the custom label `workoutplanner-live`. Keep the runner online on
   Sundays. Use a dedicated OS account and restrict repository write access
   to people you trust to run code on that machine.
2. From a local clone, under that same OS account, create the private Python
   environment and install Codex if needed:

   ```bash
   umask 077
   mkdir -p "$HOME/.local/share/workoutplanner"
   WORKOUTPLANNER_VENV="$HOME/.local/share/workoutplanner/venv" \
     bash setup/bootstrap.sh --skip-os --install-codex
   ```

3. Put the chosen athlete profile in
   `~/.local/share/workoutplanner/athlete.json`. Set its `activity_type` to
   `running`, `cycling`, or `strength_training`. Ensure the runner service
   can find `codex` on its PATH. Run `codex login` as the runner account and
   choose ChatGPT sign-in. The Garmin token does not authenticate ChatGPT.
4. In **Settings → Secrets and variables → Actions**, add a repository
   secret named `GARMIN_TOKENS_JSON`. Its value is the complete contents of
   `~/.garminconnect/garmin_tokens.json` from a successful local
   `python upload_workouts.py --login`. Treat this file as account access.
   The workflow seeds a private token cache under
   `~/.local/share/workoutplanner/garmin/` on the runner. Garmin can refresh
   that cached session between runs. If the session expires, update the
   secret with a fresh token file and remove the stale runner-side
   `garmin_tokens.json` while the workflow is idle.

## First run

In Actions, run **Weekly Garmin workout** on `master` with **Upload the
validated workout to Garmin Connect** unchecked. Review the plan and rationale
under `~/.local/share/workoutplanner/runs/` on the runner. A manual run with
the box checked, or a scheduled Sunday run, uploads after validation.
GitHub receives step status. Exports, workout plans and diagnostics stay
in the run directory on the runner. Remove old run directories when you no
longer need them.

Expired credentials or generation failures stop the run before upload.
Refresh the Garmin cache or sign in to Codex again as appropriate. If an upload fails after the
request was sent, check Garmin Connect before retrying. The uploader skips
identical workout names, and a fresh run can generate a different plan.
