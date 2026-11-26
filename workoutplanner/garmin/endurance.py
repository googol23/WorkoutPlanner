"""Map recorded, single-session FIT data to planner split and zone fields."""

LAP_FIELDS = {
    "total_distance": "distance", "total_timer_time": "duration",
    "total_elapsed_time": "elapsedDuration", "total_moving_time": "movingDuration",
    "total_ascent": "elevationGain", "total_descent": "elevationLoss",
    "avg_heart_rate": "averageHR", "max_heart_rate": "maxHR",
    "avg_power": "averagePower", "max_power": "maxPower", "normalized_power": "normalizedPower",
    "avg_speed": "averageSpeed", "max_speed": "maxSpeed",
    "enhanced_avg_speed": "averageSpeed", "enhanced_max_speed": "maxSpeed",
}


def recorded_zones(messages, field):
    sessions = messages.get("session_mesgs", [])
    references = [row for row in messages.get("time_in_zone_mesgs", [])
                  if row.get("reference_mesg") in ("session", 18) and row.get(field) is not None]
    if len(references) == 1:
        times = references[0][field]
    elif len(sessions) == 1:
        times = sessions[0].get(field)
    else:
        return []
    if not isinstance(times, list):
        return []
    # Index zero records time below zone 1. Preserve the original zone numbers.
    return [{"zoneNumber": zone, "secsInZone": seconds} for zone, seconds in enumerate(times)
            if zone > 0 and seconds is not None]


def planner_sections(messages):
    if len(messages.get("session_mesgs", [])) > 1:
        return {}
    sessions = messages.get("session_mesgs", [])
    session_sport = sessions[0].get("sport") if sessions else None
    laps = []
    for lap in messages.get("lap_mesgs", []):
        fields = {out: lap[key] for key, out in LAP_FIELDS.items() if lap.get(key) is not None}
        sport = lap.get("sport", session_sport)
        cadence = lap.get("avg_running_cadence")
        if cadence is None and sport == "running":
            cadence = lap.get("avg_cadence")
        if cadence is not None and sport in (None, "running"):
            fields["averageRunCadence"] = 2 * (cadence + (lap.get("avg_fractional_cadence") or 0))
        if fields:
            laps.append(fields)
    return {"splits": {"lapDTOs": laps} if laps else None,
            "heart_rate_zones": recorded_zones(messages, "time_in_hr_zone"),
            "power_zones": recorded_zones(messages, "time_in_power_zone")}
