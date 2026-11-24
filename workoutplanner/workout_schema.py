"""Validate workout interchange JSON independently of the Garmin client."""

import json
import math
import re
from datetime import date
from pathlib import Path


STEP_TYPES = {"warmup", "run", "interval", "recovery", "cooldown"}


class InputError(ValueError):
    """Invalid interchange-format workout."""


def fields(obj, required, optional, where):
    if not isinstance(obj, dict):
        raise InputError(f"{where} must be an object")
    missing = required - obj.keys()
    extra = obj.keys() - required - optional
    if missing or extra:
        raise InputError(f"{where}: missing {sorted(missing)}; unsupported {sorted(extra)}")


def positive(value, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise InputError(f"{where} must be a positive number")
    return value


def validate_step(step, where, depth=0):
    fields(step, {"type"}, {"duration_seconds", "target", "count", "steps", "description"}, where)
    kind = step["type"]
    if kind == "repeat":
        if depth >= 5:
            raise InputError(f"{where}: repeat nesting too deep")
        fields(step, {"type", "count", "steps"}, set(), where)
        if type(step["count"]) is not int or not 2 <= step["count"] <= 100:
            raise InputError(f"{where}.count must be an integer from 2 to 100")
        validate_steps(step["steps"], where + ".steps", depth + 1)
        return
    if kind not in STEP_TYPES:
        raise InputError(f"{where}.type must be warmup, run, interval, recovery, cooldown or repeat")
    fields(step, {"type", "duration_seconds"}, {"target", "description"}, where)
    positive(step["duration_seconds"], where + ".duration_seconds")
    if "description" in step and (not isinstance(step["description"], str) or not step["description"].strip()):
        raise InputError(f"{where}.description must be nonempty text")
    target = step.get("target")
    if target is None:
        return
    fields(target, {"type"}, {"slow_seconds_per_km", "fast_seconds_per_km", "min_bpm", "max_bpm"}, where + ".target")
    if target["type"] == "none":
        fields(target, {"type"}, set(), where + ".target")
    elif target["type"] == "pace":
        fields(target, {"type", "slow_seconds_per_km", "fast_seconds_per_km"}, set(), where + ".target")
        slow = positive(target["slow_seconds_per_km"], where + ".target.slow_seconds_per_km")
        fast = positive(target["fast_seconds_per_km"], where + ".target.fast_seconds_per_km")
        if slow < fast:
            raise InputError(f"{where}: slow pace must be >= fast pace")
    elif target["type"] == "heart_rate":
        fields(target, {"type", "min_bpm", "max_bpm"}, set(), where + ".target")
        low, high = target["min_bpm"], target["max_bpm"]
        if type(low) is not int or type(high) is not int or not 1 <= low <= high <= 250:
            raise InputError(f"{where}: heart rate must be whole bpm in ascending order (1–250)")
    else:
        raise InputError(f"{where}.target.type must be none, pace or heart_rate")


def validate_steps(steps, where, depth=0):
    if not isinstance(steps, list) or not steps:
        raise InputError(f"{where} must be a nonempty list")
    for index, step in enumerate(steps):
        validate_step(step, f"{where}[{index}]", depth)


def read_plan(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"Cannot read JSON plan: {exc}") from exc
    return data


def load_plan(path):
    return validate_plan(read_plan(path))


def validate_plan(data):
    if isinstance(data, dict) and data.get("sport") == "cycling":
        return validate_cycling_plan(data)
    fields(data, {"schema_version", "sport", "timezone", "units", "workouts"}, set(), "plan")
    if data["schema_version"] != "1.0" or data["sport"] != "running":
        raise InputError("Only schema_version 1.0 and sport running are supported")
    if not isinstance(data["timezone"], str) or not data["timezone"].strip():
        raise InputError("timezone must be a nonempty IANA timezone name")
    fields(data["units"], {"duration", "pace", "heart_rate"}, set(), "units")
    if data["units"] != {"duration": "seconds", "pace": "seconds_per_km", "heart_rate": "bpm"}:
        raise InputError("units must be seconds, seconds_per_km and bpm")
    workouts = data["workouts"]
    if not isinstance(workouts, list) or not workouts:
        raise InputError("workouts must be a nonempty list")
    names = set()
    for index, workout in enumerate(workouts):
        where = f"workouts[{index}]"
        fields(workout, {"name", "steps", "week", "total_duration_seconds"}, {"scheduled_date", "description"}, where)
        if type(workout["week"]) is not int or workout["week"] < 1:
            raise InputError(f"{where}.week must be a positive integer")
        name = workout["name"]
        if not isinstance(name, str) or not name.strip():
            raise InputError(f"{where}.name must be nonempty text")
        if name in names:
            raise InputError(f"duplicate workout name in file: {name}")
        names.add(name)
        if "description" in workout and not isinstance(workout["description"], str):
            raise InputError(f"{where}.description must be text")
        if "scheduled_date" in workout:
            value = workout["scheduled_date"]
            if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise InputError(f"{where}.scheduled_date must be YYYY-MM-DD")
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise InputError(f"{where}.scheduled_date is not a valid date") from exc
        validate_steps(workout["steps"], where + ".steps")
        if positive(workout["total_duration_seconds"], where + ".total_duration_seconds") != duration(workout["steps"]):
            raise InputError(f"{where}.total_duration_seconds does not match the steps")
    return workouts


def validate_cycling_plan(data):
    fields(data, {"schema_version", "sport", "workouts"}, set(), "cycling plan")
    if data["schema_version"] != "1.0":
        raise InputError("Cycling plan schema_version must be 1.0")
    workouts = data["workouts"]
    if not isinstance(workouts, list) or not workouts:
        raise InputError("workouts must be a nonempty list")
    names = set()
    for workout in workouts:
        fields(workout, {"name", "total_duration_seconds", "steps"}, {"scheduled_date"}, "cycling workout")
        name = workout["name"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise InputError("Cycling workout names must be nonempty and unique")
        names.add(name)
        if "scheduled_date" in workout:
            day = workout["scheduled_date"]
            if not isinstance(day, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", day):
                raise InputError("scheduled_date must be YYYY-MM-DD")
            date.fromisoformat(day)
        steps = workout["steps"]
        if not isinstance(steps, list) or not steps:
            raise InputError("Cycling steps must be a nonempty list")
        for step in steps:
            fields(step, {"type", "duration_seconds", "effort"}, {"power_watts"}, "cycling step")
            if step["type"] not in ("warmup", "ride", "recovery", "cooldown"):
                raise InputError("Cycling step type must be warmup, ride, recovery or cooldown")
            positive(step["duration_seconds"], "cycling step duration_seconds")
            if not isinstance(step["effort"], str) or not step["effort"].strip():
                raise InputError("Cycling step effort must be nonempty text")
            if "power_watts" in step:
                watts = step["power_watts"]
                fields(watts, {"min", "max"}, set(), "power_watts")
                if positive(watts["min"], "minimum watts") > positive(watts["max"], "maximum watts"):
                    raise InputError("Maximum watts must be at least minimum watts")
        if positive(workout["total_duration_seconds"], "total_duration_seconds") != duration(steps):
            raise InputError("Cycling total_duration_seconds does not match the steps")
    return workouts


def duration(steps):
    return sum(step["count"] * duration(step["steps"]) if step["type"] == "repeat" else step["duration_seconds"] for step in steps)
