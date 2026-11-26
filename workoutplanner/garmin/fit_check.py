"""Compare recorded strength fields without printing or saving the original activity."""

from io import BytesIO
from zipfile import BadZipFile, ZipFile


MAX_BYTES = 32 * 1024 * 1024


def decode_messages(archive):
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError:
        raise RuntimeError("Install setup/requirements-fit-check.txt in the project environment.") from None

    try:
        with ZipFile(BytesIO(archive)) as bundle:
            files = [entry for entry in bundle.infolist() if entry.filename.lower().endswith(".fit")]
            if len(files) != 1:
                raise RuntimeError(f"Expected one FIT file in the download, found {len(files)}.")
            if files[0].file_size > MAX_BYTES:
                raise RuntimeError("FIT file exceeds the local comparison size limit.")
            payload = bundle.read(files[0])
    except BadZipFile:
        raise RuntimeError("Garmin returned an invalid activity archive.") from None
    decoder = Decoder(Stream.from_byte_array(bytearray(payload)))
    messages, errors = decoder.read(merge_heart_rates=False)
    if errors:
        raise RuntimeError("Could not decode the complete FIT file.")
    return messages


def decode_sets(archive):
    return decode_messages(archive).get("set_mesgs", [])


def report(reference, recorded):
    print(f"Set records: existing export {len(reference)}, original FIT {len(recorded)}.")
    active = [row for row in recorded if row.get("set_type") == "active"]
    previous = [row for row in reference if str(row.get("setType")).lower() == "active"]
    print(f"Active sets: existing export {len(previous)}, original FIT {len(active)}.")
    classified = sum(row.get("category_subtype") is not None for row in active)
    print(f"FIT active sets with an exercise subtype: {classified}/{len(active)}.")
    reps = [row.get("repetitions") for row in active]
    previous_reps = [row.get("repetitionCount") for row in previous]
    if not reps or len(reps) != len(previous_reps) or None in reps or None in previous_reps:
        status = "comparison unavailable"
    else:
        status = "match in returned order" if reps == previous_reps else "differ in returned order"
    print(f"Active-set repetitions: {status}.")
    weights = [row.get("weight") for row in active]
    print(f"FIT active sets with recorded weight (kg): {sum(w is not None for w in weights)}/{len(active)}.")
    # Only compare when the reference explicitly identifies the underlying unit.
    grams = [row.get("weightInGrams") for row in previous]
    if weights and len(grams) == len(weights) and all(isinstance(v, (int, float)) for v in weights + grams):
        match = all(abs(w * 1000 - g) < 0.01 for w, g in zip(weights, grams))
        print("Active-set loads in returned order: " + ("match." if match else "differ."))
    else:
        print("Load equivalence unverified; a comparable value and explicit unit are needed for each set.")
