#!/usr/bin/env python3
"""Compatibility entry point for the WorkoutPlanner CLI."""

from workoutplanner.chatgpt.generate import main


if __name__ == "__main__":
    raise SystemExit(main())
