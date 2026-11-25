"""Share Garmin Connect authentication between the read and write tools."""

import os
from getpass import getpass
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError


TOKEN_DIR = Path(os.environ.get("WORKOUTPLANNER_GARMIN_TOKEN_DIR", Path.home() / ".garminconnect"))


def authenticate():
    try:
        api = Garmin()
        api.login(str(TOKEN_DIR))
        print("Authenticated using saved tokens.")
        return api
    except (GarminConnectAuthenticationError, FileNotFoundError) as exc:
        if os.environ.get("WORKOUTPLANNER_GARMIN_NONINTERACTIVE") == "1":
            raise GarminConnectAuthenticationError(
                "Saved Garmin login is unavailable or expired. Refresh the runner token."
            ) from exc
    email = input("Garmin email: ").strip()
    if not email:
        raise ValueError("email is required")
    password = getpass("Garmin password: ")
    api = Garmin(email=email, password=password, prompt_mfa=lambda: input("Garmin MFA code: ").strip())
    password = None
    api.login(str(TOKEN_DIR))
    print("Authenticated; reusable tokens stored outside this project.")
    return api
