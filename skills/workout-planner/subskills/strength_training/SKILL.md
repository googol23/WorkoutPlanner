---
name: strength-training-workout-planner
description: Plan or adjust one Garmin-ready gym strength session using exercise-level Garmin history, goals, equipment, preferences, cross-training fatigue, and resistance-training evidence.
---

# Gym strength training planner

Use this skill for a profile whose activity type is `strength_training`. Generate one next gym session that advances the stated goal and fits the user's equipment and time. Coordinate with the WorkoutPlanner root skill for other activity profiles.

## Review the lifter's evidence

- Check history coverage and dates. Prefer recorded exercise-level sets, repetitions, load, and units over session summary totals. Distinguish active sets from warm-up sets when the export does so. Do not assume missing exercise details mean zero work.
- Compare the same exercise and setup before progressing. Do not combine kilograms and pounds, infer a one-rep max from a set, or interpret total volume when the export's load units or counting method are unclear.
- Use recent running and cycling as recovery context, especially for lower-body and trunk fatigue. Account for pain, soreness, fatigue, and the athlete's feedback even when device summaries look favorable.
- Read `garmin_exercise_catalog` from the prompt when supplied. Select exact Garmin display names only. Match movement and equipment; similar names are not necessarily interchangeable. Apply equipment constraints as hard limits. Preferences are secondary to goal fit, safety, and availability. If no suitable catalog exercise exists, defer and ask a focused question instead of inventing a name.

## Build a balanced, realistic session

1. **Define the emphasis.** Map the goal to the session: general strength, hypertrophy, strength maintenance, or a sport-supporting session. Don't assume a goal absent from the profile. Select complementary movement patterns (knee-dominant, hip hinge/extension, push, pull, carry/core) as relevant; don't force every pattern into a short session.
2. **Set volume and effort.** Choose work sets, rep ranges, rest, and effort from experience and recent performance. Keep the dose repeatable. Use a reps-in-reserve (RIR) target only when the athlete understands it or the input uses RIR; otherwise describe a simple submaximal effort cue. Failure is not required. Avoid prescribing maximal attempts or an unsupported load.
3. **Progress conservatively.** Change load, repetitions, sets, or exercise complexity only when the same movement was tolerated and the history supports it. Prefer one progression variable at a time. After a missed or unusually fatiguing session, do not automatically make the next one harder. If exercise-level history is unavailable, start with a conservative familiar movement selection and omit loads.
4. **Respect equipment and preferences.** Prioritize a preferred machine/exercise only when the exact catalog option fits the stated gym. Do not assume a machine or bench is available from a generic word like “gym.” Include a substitute only if the contract and available time allow it; otherwise choose an available alternative.
5. **Account for total session time.** Estimate warm-up, setup/transitions, work duration, and rest between sets. Rest occurs between—not after—the final set. Keep the total at or below stated availability; a shorter, coherent session is preferable to a crowded circuit.
6. **Check cross-sport interference.** Avoid placing a high-fatigue leg session immediately beside an important run or ride in the recommendation. The athlete normally chooses one proposed option; explain how to space sessions if more than one is selected.

## Research use

Read the [strength training evidence register](../../references/strength_training-evidence.md). S1 and S2 support matching resistance-training variables to the goal and available history; group-level rankings are not mandatory prescriptions. S3 supports the conclusion that failure is not essential. Cite relevant source IDs and links in the shared rationale, and describe limits rather than presenting a study as a personalized guarantee.

## Return contract

Follow the [strength JSON output contract](../../references/strength_training-output.md). Use only exact names from `garmin_exercise_catalog` when it is present. Do not add fields, prose, invented loads, or unsupported exercises. The Garmin encoder maps the lower bound of the rep range to the watch target and preserves the range and effort cue in notes.