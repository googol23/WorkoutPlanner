"""Share Garmin Connect authentication between the read and write tools."""

from getpass import getpass
from pathlib import Path

from garminconnect import Garmin, GarminConnectAuthenticationError

from workoutplanner.garmin.contracts import ActivityReader, WorkoutPublisher


TOKEN_DIR = Path.home() / ".garminconnect"


def authenticate() -> Garmin:
    try:
        api = Garmin()
        api.login(str(TOKEN_DIR))
        print("Authenticated using saved tokens.")
        return api
    except (GarminConnectAuthenticationError, FileNotFoundError):
        pass
    email = input("Garmin email: ").strip()
    if not email:
        raise ValueError("email is required")
    password = getpass("Garmin password: ")
    api = Garmin(email=email, password=password, prompt_mfa=lambda: input("Garmin MFA code: ").strip())
    password = None
    api.login(str(TOKEN_DIR))
    print("Authenticated; reusable tokens stored outside this project.")
    return api


def open_activity_reader() -> ActivityReader:
    return authenticate()


def open_workout_publisher() -> WorkoutPublisher:
    return authenticate()
