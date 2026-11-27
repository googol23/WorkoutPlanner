"""Configure a Garmin Personal API key and read a single activity on Linux."""

import argparse
from getpass import GetPassWarning, getpass
from http.client import HTTPException, HTTPSConnection
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import warnings
from workoutplanner.garmin import fit_check


HOST = "personal.connectapi.garmin.com"
TOKEN_PATH = "/personalapitoken-service/personal-api/personal-api-key/token"
KEY_FILE = Path(__file__).resolve().parents[2] / "private" / "garmin_personal_api_key"


def save_key(key):
    key = credential(key)
    directory = KEY_FILE.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    fd, temporary = tempfile.mkstemp(prefix=".garmin-key-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(key + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, KEY_FILE)
        os.chmod(KEY_FILE, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_key():
    try:
        info = KEY_FILE.lstat()
    except FileNotFoundError:
        raise RuntimeError(f"Personal API key file not found at {KEY_FILE}. Run the login command.") from None
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError("Personal API key must be stored in a regular file.")
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError(f"Personal API key file is accessible to other users. Run: chmod 600 {KEY_FILE}")
    try:
        return credential(KEY_FILE.read_text(encoding="utf-8").strip())
    except OSError:
        raise RuntimeError("Could not read the Personal API key file.") from None


def request(method, path, authorization, *, optional=False, accept="*/*", limit=None):
    conn = HTTPSConnection(HOST, timeout=30)
    try:
        conn.request(method, path, headers={"Authorization": authorization, "Accept": accept})
        response = conn.getresponse()
        if optional and response.status in (204, 404):
            return b""
        if response.status in (401, 403):
            raise RuntimeError("Garmin denied access. Check key expiry and permissions, then run login.")
        if response.status != 200:
            raise RuntimeError(f"Garmin returned HTTP {response.status}.")
        if limit is None:
            return response.read()
        payload = response.read(limit + 1)
        if len(payload) > limit:
            raise RuntimeError("Garmin download exceeds the local comparison size limit.")
        return payload
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
    save_key(key)
    print(f"Garmin accepted the key. Saved it to {KEY_FILE} with owner-only permissions.")


def exercise_set_groups(value):
    """Find explicitly named exerciseSets lists in a JSON object or array."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "exerciseSets" and isinstance(child, list):
                yield child
            else:
                yield from exercise_set_groups(child)
    elif isinstance(value, list):
        for child in value:
            yield from exercise_set_groups(child)


def describe_sets(source, groups):
    if not groups:
        print(f"{source}: exerciseSets field unavailable.")
    else:
        count = sum(map(len, groups))
        print(f"{source}: {count} exercise-set records across {len(groups)} list(s).")


def reference_sets(activity_id, legacy_export):
    records = json.loads(legacy_export.read_text())["activities"]
    previous = next((row for row in records if str(row["activity_id"]) == str(activity_id)), None)
    if previous is None:
        raise RuntimeError("The selected activity is missing from the comparison export.")
    return list(exercise_set_groups(previous.get("exercise_sets")))


def check_fit(activity_id, legacy_export):
    groups = reference_sets(activity_id, legacy_export)
    if len(groups) != 1:
        raise RuntimeError("Expected one exercise-set list in the existing export.")
    token = exchange(load_key())
    fit_check.report(groups[0], read_fit_sets(activity_id, "Bearer " + token))


def read_fit_messages(activity_id, authorization, *, optional=False):
    archive = request("GET", f"/download-service/files/activity/{activity_id}", authorization,
                      accept="application/zip, application/x-zip-compressed, application/octet-stream",
                      limit=fit_check.MAX_BYTES, optional=optional)
    if not archive and optional:
        return {}
    return fit_check.decode_messages(archive)


def read_fit_sets(activity_id, authorization, *, optional=False):
    return read_fit_messages(activity_id, authorization, optional=optional).get("set_mesgs", [])


def check(activity_id, legacy_export=None):
    token = exchange(load_key())
    activity = json.loads(request("GET", f"/activity-service/activity/{activity_id}", "Bearer " + token))
    if not isinstance(activity, dict) or str(activity.get("activityId")) != str(activity_id):
        raise RuntimeError("Garmin returned an unexpected activity.")
    print("Personal API returned the requested activity.")
    if legacy_export is None:
        return
    legacy = reference_sets(activity_id, legacy_export)
    current = list(exercise_set_groups(activity))
    describe_sets("Existing export", legacy)
    describe_sets("Personal API activity detail", current)
    if not any(current):
        path = f"/activity-service/activity/{activity_id}/workouts"
        raw = request("GET", path, "Bearer " + token, optional=True)
        current = list(exercise_set_groups(json.loads(raw))) if raw else []
        describe_sets("Personal API associated workouts", current)
    if not any(legacy) or not any(current):
        print("Recorded set coverage could not be verified.")
    elif len(legacy) == len(current) == 1 and current == legacy:
        print("The returned exercise sets match the previous export exactly.")
    else:
        print("Exercise-set records differ or span multiple lists. Verify metric coverage.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login", help="verify and save or replace your personal key")
    probe = commands.add_parser("check", help="read a known activity by Garmin ID")
    probe.add_argument("activity_id", type=int)
    probe.add_argument("--compare-export", type=Path, help="compare exercise sets with a local activity export")
    fit = commands.add_parser("check-fit", help="compare the original FIT with a saved strength export")
    fit.add_argument("activity_id", type=int)
    fit.add_argument("--compare-export", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command != "login" and args.activity_id < 1:
        parser.error("activity_id must be positive")
    try:
        if args.command == "login":
            login()
        elif args.command == "check-fit":
            check_fit(args.activity_id, args.compare_export)
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
