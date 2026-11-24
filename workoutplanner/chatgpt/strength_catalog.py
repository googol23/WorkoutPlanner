"""Select prompt-sized choices from the complete local Garmin catalog."""

import re

from workoutplanner.planning_input import read_object


MAX_MACHINE_MATCHES = 24


def normalized(text):
    return " ".join(re.findall(r"\w+", text.casefold()))


def select_catalog(reference_dir, athlete, existing_exercises=()):
    catalog = read_object(reference_dir / "garmin-strength-exercises.json")
    defaults = read_object(reference_dir / "strength-default-exercises.json")
    names = {normalized(name): name for group in catalog.values() for name in group}

    preferred = []
    for request in [*athlete.get("preferred_exercises", ()), *existing_exercises]:
        key = normalized(request)
        if key == "glute bridge":
            key = "hip raise"
        if key in names:
            preferred.append(names[key])

    matches = []
    machine_terms = [normalized(term).removesuffix(" machine") for term in athlete.get("preferred_machines", ())]
    for term in machine_terms:
        if not term:
            continue
        matches.extend(name for key, name in names.items() if f" {term} " in f" {key} ")
    machine_choices = list(dict.fromkeys(matches))[:MAX_MACHINE_MATCHES]

    if preferred:
        defaults["preferred_or_existing"] = list(dict.fromkeys(preferred))
    if machine_choices:
        defaults["machine_matches"] = machine_choices
    return defaults
