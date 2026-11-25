#!/usr/bin/env python3
"""Generate a workout through Codex signed in with your ChatGPT account."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from workoutplanner.chatgpt.prompt import build_prompt, validate_existing_plan
from workoutplanner.planning_input import read_object
from workoutplanner.private_io import write_private


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "workout_json": {"type": ["string", "null"]},
    },
    "required": ["rationale", "workout_json"],
    "additionalProperties": False,
}

RESPONSE_INSTRUCTIONS = """
Return the rationale, sources or clarification in rationale. Put the complete
workout JSON object in workout_json as a JSON-encoded string without Markdown
fences. Set workout_json to null if no workout should be prescribed.
Use only the provided input and evidence. Do not run commands or access files.

"""


CODEX_ENV_KEYS = {
    "PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "APPDATA", "LOCALAPPDATA",
    "CODEX_HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "CODEX_CA_CERTIFICATE",
}


def run_codex(prompt, *, debug_file=None):
    env = {key: value for key, value in os.environ.items()
           if key.upper() in CODEX_ENV_KEYS}
    status = subprocess.run(
        ["codex", "login", "status"], env=env, capture_output=True, text=True, timeout=15,
    )
    if status.returncode or "logged in using chatgpt" not in (status.stdout + status.stderr).lower():
        raise ValueError("Run codex login and sign in with ChatGPT before generating a workout")

    help_result = subprocess.run(
        ["codex", "exec", "--help"], env=env, capture_output=True, text=True, timeout=15,
    )
    required_flags = ("--ignore-user-config", "--ephemeral", "--output-schema", "--output-last-message")
    help_text = help_result.stdout + help_result.stderr
    missing = [flag for flag in required_flags if flag not in help_text]
    if help_result.returncode or missing:
        detail = ", ".join(missing) or "codex exec --help failed"
        raise ValueError(f"Update the Codex CLI before generating a workout. Required options unavailable: {detail}")

    with TemporaryDirectory() as folder:
        workdir = Path(folder)
        schema = workdir / "response.schema.json"
        response = workdir / "response.json"
        schema.write_text(json.dumps(RESPONSE_SCHEMA), encoding="utf-8")
        result = subprocess.run(
            ["codex", "exec", "--skip-git-repo-check", "--ephemeral",
             "--sandbox", "read-only", "--ignore-user-config",
             "-c", 'approval_policy="never"',
             "-c", 'forced_login_method="chatgpt"', "-c", 'web_search="disabled"',
             "-c", f"sqlite_home={json.dumps(str(workdir))}",
             "-c", f"log_dir={json.dumps(str(workdir))}",
             "--output-schema", str(schema), "--output-last-message", str(response), "-"],
            cwd=workdir, env=env, input=RESPONSE_INSTRUCTIONS + prompt,
            capture_output=True, text=True, encoding="utf-8", timeout=300,
        )
        if result.returncode:
            if debug_file and result.stderr:
                write_private(debug_file, result.stderr)
                print(f"Codex diagnostics saved to {debug_file}", file=sys.stderr)
            raise ValueError(f"Codex generation failed (exit {result.returncode}); rerun with --debug for CLI diagnostics")
        return read_object(response)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--planning-input", required=True, type=Path)
    parser.add_argument("--existing-plan", type=Path)
    parser.add_argument("--workout-name")
    parser.add_argument("--output", type=Path, default=Path("next_workout.json"))
    parser.add_argument("--debug", action="store_true", help="save Codex stderr to a private file on failure")
    args = parser.parse_args(argv)
    if (args.existing_plan is None) != (args.workout_name is None):
        parser.error("--existing-plan and --workout-name must be supplied together")
    rationale_file = args.output.with_suffix(args.output.suffix + ".rationale.txt")
    debug_file = args.output.with_suffix(args.output.suffix + ".debug.txt") if args.debug else None
    destinations = {path.resolve() for path in (args.output, rationale_file, debug_file) if path}
    if any(path is not None and path.resolve() in destinations
           for path in (args.planning_input, args.existing_plan)):
        parser.error("--output must be different from the input files")

    try:
        planning_input = read_object(args.planning_input)
        existing_plan = read_object(args.existing_plan) if args.existing_plan else None
        response = run_codex(build_prompt(planning_input, existing_plan, args.workout_name), debug_file=debug_file)
        rationale = response.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip() or "workout_json" not in response:
            raise ValueError("Codex returned an invalid workout response")
        raw_workout = response["workout_json"]
        write_private(rationale_file, rationale + "\n")
        print(f"Rationale saved to {rationale_file}")
        if raw_workout is None:
            print("No workout was written. Review the saved response.", file=sys.stderr)
            return 2
        if not isinstance(raw_workout, str):
            raise ValueError("Codex returned invalid workout JSON")
        workout = json.loads(raw_workout)
        if not isinstance(workout, dict):
            raise ValueError("The workout must be a JSON object")
        validate_existing_plan(workout, planning_input["target_activity_type"])
        write_private(args.output, json.dumps(workout, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
        print(f"Saved {args.output}")
        return 0
    except FileNotFoundError as exc:
        detail = "Install the Codex CLI and run codex login" if exc.filename == "codex" else str(exc)
        print(f"Error: {detail}", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("Error: Codex timed out", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
