# Weekly Garmin workout on GitHub

The workflow runs Sundays at 08:17 Europe/Berlin on a GitHub-hosted Ubuntu
runner. HomeOffice can be off. The repository must be private and the default
branch must be `master`. The scheduled job syncs Garmin history, generates
one workout with Codex, validates it, and uploads the workout template.

## Configure once

Under **Settings → Secrets and variables → Actions → New repository secret**,
create these three repository secrets:

| Name | Value |
| --- | --- |
| `GARMIN_TOKENS_JSON` | Full JSON from `~/.garminconnect/garmin_tokens.json` after a successful local Garmin login. |
| `CODEX_AUTH_JSON` | Full JSON from `~/.codex/auth.json` after signing in to Codex with ChatGPT. File-based credential storage is required. |
| `ATHLETE_PROFILES_JSON` | A JSON object keyed by profile name. Each profile includes `activity_type`, `goals`, and `availability`. |

Keep the login files out of Git, chat, and logs. GitHub stores these secrets
and the trusted job receives their contents at runtime. Limit write access
to trustworthy collaborators. Update `ATHLETE_PROFILES_JSON` when a profile
changes. The selected profile is the only one used for generation.

### Profile example

```json
{
  "running": {
    "activity_type": "running",
    "goals": "Build endurance for a 10 km run",
    "availability": "30 minutes"
  },
  "cycling": {
    "activity_type": "cycling",
    "goals": "Build endurance for longer weekend rides",
    "availability": "90 minutes",
    "equipment": "Outdoor road bike"
  },
  "strength": {
    "activity_type": "strength_training",
    "goals": "Build full-body strength",
    "availability": "40 minutes",
    "equipment": "Dumbbells, bench, leg press and cable station",
    "preferred_machines": ["Leg Press"],
    "preferred_exercises": ["Dumbbell Bench Press"]
  }
}
```

Under **Settings → Secrets and variables → Actions → Variables**, set
`WORKOUTPLANNER_SUNDAY_PROFILE` to a profile name such as `cycling`.
If unset, Sundays use `running`. For a manual run, enter a profile name
or leave it blank to use the Sunday default. Multiple names can use the
same sport.

### Codex login secret

`CODEX_AUTH_JSON` is the complete file created by Codex after ChatGPT login.
On the machine where you sign in, use file-based credential storage if
needed:

```bash
codex -c 'cli_auth_credentials_store="file"' login
codex -c 'cli_auth_credentials_store="file"' login status
test -s "$HOME/.codex/auth.json" && echo "Codex login file exists"
```

Choose ChatGPT sign-in and copy the actual file into the secret value in
GitHub. A hand-written JSON example cannot authenticate a run.

## First run

Open **Actions → Weekly Garmin workout → Run workflow** and select `master`.
Leave **Upload** unchecked to test live sync and ChatGPT generation through
offline validation. Once that passes, a manual run with **Upload** checked
uploads the generated workout. A scheduled Sunday run uploads automatically.
Verify the workout in Garmin Connect. The workflow creates a workout template,
and calendar placement remains a separate operation.

The job reports step status. It does not attach exports, plans, or diagnostics
to the run. Credentials and personal files are removed from temporary runner
storage at the end of the job. The job does not save token changes back to
GitHub, so if either cached session expires or its refresh token rotates,
sign in again locally and replace the corresponding secret. If upload fails
after the request was sent, check Garmin Connect before retrying.
