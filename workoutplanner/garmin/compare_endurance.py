"""Compare planner inputs from two Garmin readers for a recorded run and ride."""

from math import isfinite
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


def compare_rows(section, left, right):
    print(f"  {section} rows: legacy {len(left)}, personal {len(right)}")
    if section == "first_splits":
        for field in ("averageSpeed", "maxSpeed"):
            differences = [abs(old[field] - new[field]) for old, new in zip(left, right)
                           if all(type(row.get(field)) in (int, float) and isfinite(row[field])
                                  for row in (old, new))]
            if differences:
                print(f"    {field} largest absolute difference: {max(differences):.6g} m/s "
                      f"across {len(differences)} comparable laps")
        pairs = zip(left, right)
    else:
        # Garmin Connect and the FIT file can return different zone orders.
        maps = []
        for rows in (left, right):
            keyed = {row.get("zoneNumber", row.get("zone")): row for row in rows}
            if None in keyed or len(keyed) != len(rows):
                print("    Cannot align zones: missing or duplicate zone numbers.")
                return
            maps.append(keyed)
        legacy, personal = maps
        for label, source, other in (("legacy", legacy, personal), ("personal", personal, legacy)):
            extra = source.keys() - other.keys()
            if extra:
                print(f"    {label}-only zone numbers: {', '.join(sorted(map(str, extra)))}")
                times = [source[key].get("secsInZone", source[key].get("secondsInZone")) for key in extra]
                valid = [t for t in times if type(t) in (int, float) and isfinite(t) and t >= 0]
                positive = sum(t > 0 for t in valid)
                print(f"    {label}-only zones with positive time: {positive}; "
                      f"zero: {len(valid) - positive}; unknown: {len(times) - len(valid)}")
        pairs = ((legacy[key], personal[key]) for key in legacy.keys() & personal.keys())

    compared = {}
    for old, new in pairs:
        for key in old.keys() | new.keys():
            counts = compared.setdefault(key, [0, 0, 0, 0])
            if key not in new:
                counts[2] += 1
            elif key not in old:
                counts[3] += 1
            elif old[key] == new[key]:
                counts[0] += 1
            else:
                counts[1] += 1
    if compared:
        print("    field: exact / different / legacy only / personal only (aligned rows)")
        for key, counts in sorted(compared.items()):
            print(f"    {key}: " + " / ".join(map(str, counts)))


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
        for section in ("first_splits", "heart_rate_zones", "power_zones"):
            left, right = before.get(section, []), after.get(section, [])
            if left != right:
                compare_rows(section, left, right)


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
