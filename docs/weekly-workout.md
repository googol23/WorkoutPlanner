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
| `ATHLETE_PROFILE_JSON` | Full athlete profile JSON. It must include a supported `activity_type`, `goals`, and `availability`. |

Keep the login files out of Git, chat, and logs. GitHub stores these secrets
and the trusted job receives their contents at runtime. Limit write access
to trustworthy collaborators. Use names from the existing local profiles
and update `ATHLETE_PROFILE_JSON` whenever goals or equipment change.

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
