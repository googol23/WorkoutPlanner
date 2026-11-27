---
name: cycling-workout-planner
description: Plan or adjust one Garmin-ready cycling workout using cycling goals, recent rides, all-sport recovery context, available equipment, and cycling research.
---

# Cycling workout planner

Use this skill for a profile whose activity type is `cycling`. Return one next ride option for the profile's actual cycling goal, equipment, time budget, and recent tolerance. When the profile describes another sport, only treat cycling as cross-training if the profile explains that role.

## Review the rider's evidence

- Check the history window, ride dates, reported counts, and missing fields. Separate rides from runs and gym sessions; use the latter to judge overall fatigue and leg/upper-body recovery, not to invent cycling performance.
- Compare like with like: indoor/outdoor, route, surface, elevation, wind, temperature, traffic, and duration. Review moving and elapsed time, distance, elevation, average/max heart rate, cadence, power/normalized power, zone time, training effect/load, and subjective effort when available. Coasting, descents, drafting, and stop time make speed a weak effort measure.
- Use FTP and power zones only when the profile supplies a credible current value or the history identifies a recent test and its units. Confirm the power target is appropriate to the same bike/sensor and cycling context. Use heart-rate ranges only with known cycling zone settings. Otherwise specify RPE, talk test, cadence intent, or terrain cues without inventing numeric thresholds.
- Treat Garmin load and training effect as device estimates, and exported activity history as potentially incomplete.

## Select and dose the next ride

1. **Check readiness across sports.** Consider recent hard rides, running intensity, leg-dominant strength work, fatigue, soreness, pain, and the athlete's reported recovery. If symptoms make cycling unsafe, defer rather than using a low-effort prescription to mask them.
2. **Choose one purpose.** Options include easy endurance, sustained aerobic riding, tempo/threshold intervals, short high-intensity intervals, cadence practice, climbing, or goal-specific time-on-bike. For multi-day bikepacking, build durable aerobic time and comfort progressively; a single indoor interval session is not a substitute for long-ride or consecutive-day tolerance.
3. **Set the dose from comparable rides.** Fit total duration to availability and recent tolerated ride duration. When ride history is sparse, ask for typical duration/equipment if needed; otherwise offer a conservative, conversational ride. Do not translate a target trip distance into a workout distance without route, terrain, and speed context. Avoid fixed weekly increases or copying a study's exact protocol.
4. **Specify work and recovery together.** For intervals, state the number and duration of work bouts, effort/target, and recovery duration/effort. Use watts only when benchmarked; otherwise use clear effort cues. Include easy warm-up and cool-down as needed.
5. **Check feasibility.** Sum all step durations exactly and remain within the time budget. Use only available equipment (for example, don't prescribe trainer power targets if the athlete rides outdoors without power measurement). Leave scheduling dates out unless requested.

## Research use

Read the [cycling evidence register](../../references/cycling-evidence.md). C1 supports pairing interval duration with effort and scaling work/recovery to the rider. C2 supports considering intensity alongside easy volume; neither provides a universal distribution or a ready-made individual workout. Cite relevant IDs and links in the rationale, with evidence limits.

## Return contract

Follow the [cycling JSON output contract](../../references/cycling-output.md). Return one standalone `schema_version: "1.0"`, `sport: "cycling"` object, without extra fields or rationale inside the JSON. Garmin accepts timed `warmup`, `ride`, `recovery`, and `cooldown` steps with effort cues and optional supported watt ranges. Check arithmetic and emit no upload or scheduling claim.