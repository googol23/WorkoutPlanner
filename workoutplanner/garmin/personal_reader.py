"""Read Personal API activity summaries and recorded strength sets."""

import json
from urllib.parse import urlencode

from workoutplanner.garmin import personal


class PersonalReader:
    def __init__(self):
        self._authorization = "Bearer " + personal.exchange(personal.keyring("lookup"))

    def _search(self, **params):
        path = "/activitylist-service/activities/search/activities?" + urlencode(params)
        page = json.loads(personal.request("GET", path, self._authorization))
        if not isinstance(page, list) or any(not isinstance(row, dict) or
                                             not str(row.get("activityId")).isdecimal() for row in page):
            raise RuntimeError("Unexpected Personal API activity search response.")
        return page

    def get_activities(self, *, start, limit, activitytype=None):
        filters = {"activityType": activitytype} if activitytype else {}
        return self._search(start=start, limit=limit, **filters)

    def get_activities_by_date(self, start, end):
        rows = []
        seen = set()
        offset = 0
        while True:
            page = self._search(start=offset, limit=20, startDate=start, endDate=end)
            before = len(seen)
            for row in page:
                key = str(row["activityId"])
                if key not in seen:
                    seen.add(key)
                    rows.append(row)
            if len(page) < 20:
                return rows
            if len(seen) == before:
                raise RuntimeError("Personal API activity pagination did not advance.")
            offset += len(page)

    def get_activity(self, activity_id):
        activity = json.loads(personal.request("GET", f"/activity-service/activity/{activity_id}",
                                               self._authorization))
        if not isinstance(activity, dict) or str(activity.get("activityId")) != activity_id:
            raise RuntimeError("Personal API returned an unexpected activity.")
        return activity

    def get_activity_exercise_sets(self, activity_id):
        records = personal.read_fit_sets(activity_id, self._authorization, optional=True)
        sets = []
        for record in records:
            row = {}
            for source, dest in (("repetitions", "repetitionCount"), ("duration", "duration"),
                                 ("category", "category"), ("category_subtype", "categorySubtype")):
                if record.get(source) is not None:
                    row[dest] = record[source]
            if record.get("set_type") is not None:
                row["setType"] = str(record["set_type"]).upper()
            if record.get("weight") is not None:
                row.update(load=record["weight"], loadUnit="kg")
            sets.append(row)
        return {"source": "original_fit", "exerciseSets": sets}
