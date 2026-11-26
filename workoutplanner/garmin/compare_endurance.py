"""Compare planner inputs from two Garmin readers for a recorded run and ride."""

import sys

from garminconnect import (
    GarminConnectAuthenticationError, GarminConnectConnectionError,
    GarminConnectNotFoundError, GarminConnectTooManyRequestsError,
)

from workoutplanner.chatgpt.history import SPORT_TYPE_KEYS, summarize_activity
from workoutplanner.garmin.auth import open_activity_reader
from workoutplanner.garmin.download import export_activity, type_key
from workoutplanner.garmin.personal_reader import PersonalReader


def latest(reader, sport):
    # The Personal API search accepts a parent sport and returns its subtypes.
    seen = set()
    offset = 0
    while True:
        page = reader.get_activities(start=offset, limit=20, activitytype=sport)
        for row in page:
            if not row.get("inProgress") and type_key(row) in SPORT_TYPE_KEYS[sport]:
                return row
        if len(page) < 20:
            return None
        ids = {str(row["activityId"]) for row in page}
        if ids <= seen:
            raise RuntimeError("Activity search repeated a page.")
        seen.update(ids)
        offset += len(page)


def report(label, reference, personal):
    reference_keys = set(reference)
    personal_keys = set(personal)
    common = reference_keys & personal_keys
    changed = {key for key in common if reference[key] != personal[key]}
    print(f"  {label}: {len(common) - len(changed)} matching fields")
    for status, keys in (("legacy only", reference_keys - personal_keys),
                         ("personal only", personal_keys - reference_keys),
                         ("different", changed)):
        if keys:
            print(f"    {status}: {', '.join(sorted(keys))}")


def compare(legacy, personal):
    for sport in ("running", "cycling"):
        listing = latest(personal, sport)
        if listing is None:
            print(f"{sport}: no completed activity found in this sport search.")
            continue
        summaries = []
        for reader in (legacy, personal):
            record = export_activity(reader, listing, activity_type="all")
            summaries.append(summarize_activity(record))
        before, after = summaries
        print(f"{sport}: same recorded session")
        report("summary metrics", before.pop("summary"), after.pop("summary"))
        for row in summaries:
            row.pop("unavailable_fields", None)
        report("other planner fields", before, after)


def main():
    try:
        compare(open_activity_reader(), PersonalReader())
        return 0
    except (GarminConnectAuthenticationError, GarminConnectConnectionError, GarminConnectNotFoundError,
            GarminConnectTooManyRequestsError, OSError, RuntimeError, ValueError, EOFError) as exc:
        print(f"Comparison failed ({type(exc).__name__}). Check both local Garmin logins and connectivity.",
              file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
