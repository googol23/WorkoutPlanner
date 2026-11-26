"""Configure a Garmin Personal API key and read a single activity on Linux."""

import argparse
from getpass import GetPassWarning, getpass
from http.client import HTTPException, HTTPSConnection
import json
from pathlib import Path
import re
import subprocess
import sys
import warnings


HOST = "personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
ATTRIBUTES = ["application", "workoutplanner", "credential", "garmin-personal-api"]


def keyring(command, key=None):
    args = ["secret-tool", command]
    if command == "store":
        args += ["--label=WorkoutPlanner Garmin Personal API"]
    try:
        result = subprocess.run(args + ATTRIBUTES, input=key or "", capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError("Install libsecret-tools and use a desktop Secret Service keyring.") from None
    if result.returncode:
        raise RuntimeError("Check that your desktop keyring is unlocked and run the login command.")
    return result.stdout.strip()


def request(method, path, authorization):
    conn = HTTPSConnection(HOST, timeout=30)
    try:
        conn.request(method, path, headers={"Authorization": authorization, "Accept": "*/*"})
        response = conn.getresponse()
        if response.status in (401, 403):
            raise RuntimeError("Garmin denied access. Check key expiry and permissions, then run login.")
        if response.status != 200:
            raise RuntimeError(f"Garmin returned HTTP {response.status}.")
        return response.read()
    except (OSError, HTTPException):
        raise RuntimeError("Could not complete the HTTPS request to Garmin.") from None
    finally:
        conn.close()


def credential(value):
    if not value or not value.isascii() or not value.isprintable() or any(c.isspace() for c in value):
        raise RuntimeError("Expected a single nonempty credential. Run login to set the key.")
    return value


def exchange(key):
    raw = request("POST", TOKEN_PATH, "ApiKey " + credential(key))
    token = raw.strip()
    if not re.fullmatch(rb"[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+){2}", token):
        raise RuntimeError("Garmin returned an invalid access token.")
    return token.decode("ascii")


def login():
    # getpass can otherwise fall back to an echoed prompt without a terminal.
    with warnings.catch_warnings():
        warnings.simplefilter("error", GetPassWarning)
        try:
            key = getpass("Garmin Personal API key: ").strip()
        except GetPassWarning:
            raise RuntimeError("Run login in an interactive terminal with hidden input.") from None
    exchange(key)
    keyring("store", key)
    print("Garmin accepted the key. Saved it in your desktop keyring.")


def check(activity_id, legacy_export=None):
    token = exchange(keyring("lookup"))
    activity = json.loads(request("GET", f"/activity-service/activity/{activity_id}", "Bearer " + token))
    if not isinstance(activity, dict) or str(activity.get("activityId")) != str(activity_id):
        raise RuntimeError("Garmin returned an unexpected activity.")
    print("Personal API returned the requested activity.")
    if legacy_export is None:
        return
    records = json.loads(legacy_export.read_text())["activities"]
    previous = next((row for row in records if str(row["activity_id"]) == str(activity_id)), None)
    if previous is None:
        raise RuntimeError("The selected activity is missing from the comparison export.")
    legacy = (previous.get("exercise_sets") or {}).get("exerciseSets")
    current = activity.get("exerciseSets")
    if not legacy or not current:
        print("Set comparison unavailable: one or both responses lack exercise sets.")
    elif current == legacy:
        print("The returned exercise sets match the previous export exactly.")
    else:
        print("Exercise-set records differ. Metric parity requires further verification.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login", help="verify and save or replace your personal key")
    probe = commands.add_parser("check", help="read a known activity by Garmin ID")
    probe.add_argument("activity_id", type=int)
    probe.add_argument("--compare-export", type=Path, help="compare exercise sets with a local activity export")
    args = parser.parse_args(argv)
    if args.command == "check" and args.activity_id < 1:
        parser.error("activity_id must be positive")
    try:
        if args.command == "login":
            login()
        else:
            check(args.activity_id, args.compare_export)
        return 0
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (EOFError, OSError, ValueError, KeyError, TypeError, AttributeError):
        print("Error: Could not read input or decode the activity response.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
