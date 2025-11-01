"""Anki SM-2 spaced repetition scheduler implementation."""
from __future__ import annotations
import datetime as dt
import os
from typing import Tuple

# Anki defaults
MIN_EASE_FACTOR = 1.3
DEFAULT_EASE_FACTOR = 2.5
MAX_EASE_FACTOR = 2.5  # Initial maximum

# Learning steps in minutes (configurable via env)
DEFAULT_LEARNING_STEPS = [1, 10]  # 1 minute, 10 minutes
DEFAULT_RELEARNING_STEPS = [10]  # 10 minutes for lapses

# Graduation intervals
DEFAULT_GRADUATING_INTERVAL = 1  # days
DEFAULT_EASY_INTERVAL = 4  # days

TZ = dt.timezone.utc


def get_learning_steps() -> list[int]:
    """Get learning steps from environment or use defaults."""
    env_steps = os.getenv("ANKI_LEARNING_STEPS", "1,10")
    try:
        return [int(x.strip()) for x in env_steps.split(",")]
    except (ValueError, AttributeError):
        return DEFAULT_LEARNING_STEPS


def get_relearning_steps() -> list[int]:
    """Get relearning steps from environment or use defaults."""
    env_steps = os.getenv("ANKI_RELEARNING_STEPS", "10")
    try:
        return [int(x.strip()) for x in env_steps.split(",")]
    except (ValueError, AttributeError):
        return DEFAULT_RELEARNING_STEPS


def update_ease_factor(ease_factor: float, quality: int) -> float:
    """Update ease factor based on response quality.
    
    Anki SM-2 formula: EF = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    Where q is quality (0-4 in our system, 0-5 in original SM-2)
    """
    # Convert 0-4 to 1-5 scale for SM-2 formula
    q = quality + 1
    
    new_ef = ease_factor + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    return max(MIN_EASE_FACTOR, new_ef)


def schedule_new_card(now: dt.datetime, quality: int, step_index: int = 0) -> Tuple[dt.datetime, str, int, float]:
    """Schedule a new card based on quality rating.
    
    Returns: (due_time, phase, step_index, ease_factor)
    """
    learning_steps = get_learning_steps()
    
    if quality < 3:  # Again (0), Hard (1), or difficult Good (2)
        # Stay in learning, reset to first step
        step_index = 0
        due_time = now + dt.timedelta(minutes=learning_steps[0])
        return due_time, "learn", step_index, DEFAULT_EASE_FACTOR
    
    if quality == 3:  # Good
        # Progress through learning steps
        if step_index + 1 < len(learning_steps):
            step_index += 1
            due_time = now + dt.timedelta(minutes=learning_steps[step_index])
            return due_time, "learn", step_index, DEFAULT_EASE_FACTOR
        else:
            # Graduate to review
            due_time = now + dt.timedelta(days=DEFAULT_GRADUATING_INTERVAL)
            return due_time, "review", 0, DEFAULT_EASE_FACTOR
    
    else:  # Easy (4)
        # Skip learning steps, go straight to review with easy interval
        due_time = now + dt.timedelta(days=DEFAULT_EASY_INTERVAL)
        return due_time, "review", 0, DEFAULT_EASE_FACTOR


def schedule_learning_card(now: dt.datetime, quality: int, step_index: int, ease_factor: float) -> Tuple[dt.datetime, str, int, float]:
    """Schedule a card currently in learning phase.
    
    Returns: (due_time, phase, step_index, ease_factor)
    """
    learning_steps = get_learning_steps()
    
    if quality < 3:  # Again, Hard, or difficult Good
        # Reset to first learning step
        step_index = 0
        due_time = now + dt.timedelta(minutes=learning_steps[0])
        return due_time, "learn", step_index, ease_factor
    
    if quality == 3:  # Good
        # Progress to next step or graduate
        if step_index + 1 < len(learning_steps):
            step_index += 1
            due_time = now + dt.timedelta(minutes=learning_steps[step_index])
            return due_time, "learn", step_index, ease_factor
        else:
            # Graduate to review
            due_time = now + dt.timedelta(days=DEFAULT_GRADUATING_INTERVAL)
            return due_time, "review", 0, ease_factor
    
    else:  # Easy (4)
        # Graduate immediately with easy interval
        due_time = now + dt.timedelta(days=DEFAULT_EASY_INTERVAL)
        return due_time, "review", 0, ease_factor


def schedule_review_card(now: dt.datetime, quality: int, interval_days: int, ease_factor: float) -> Tuple[dt.datetime, str, int, float, int]:
    """Schedule a card in review phase.
    
    Returns: (due_time, phase, step_index, ease_factor, new_interval_days)
    """
    if quality < 3:  # Again, Hard, or difficult Good - card lapses
        # Enter relearning
        relearning_steps = get_relearning_steps()
        due_time = now + dt.timedelta(minutes=relearning_steps[0])
        new_ease_factor = max(MIN_EASE_FACTOR, ease_factor - 0.2)
        return due_time, "relearn", 0, new_ease_factor, 0
    
    # Update ease factor for successful reviews
    new_ease_factor = update_ease_factor(ease_factor, quality)
    
    if quality == 3:  # Good
        # Normal interval calculation
        new_interval = max(1, round(interval_days * new_ease_factor))
    
    elif quality == 4:  # Easy
        # Longer interval for easy cards
        easy_bonus = float(os.getenv("ANKI_EASY_BONUS", "1.3"))  # Default 1.3x bonus
        new_interval = max(1, round(interval_days * new_ease_factor * easy_bonus))
    
    # Apply maximum interval limit if configured
    max_interval = int(os.getenv("ANKI_MAX_INTERVAL_DAYS", "36500"))  # ~100 years default
    new_interval = min(new_interval, max_interval)
    
    due_time = now + dt.timedelta(days=new_interval)
    return due_time, "review", 0, new_ease_factor, new_interval


def schedule_relearning_card(now: dt.datetime, quality: int, step_index: int, ease_factor: float) -> Tuple[dt.datetime, str, int, float]:
    """Schedule a card currently in relearning phase.
    
    Returns: (due_time, phase, step_index, ease_factor)
    """
    relearning_steps = get_relearning_steps()
    
    if quality < 3:  # Again, Hard, or difficult Good
        # Reset to first relearning step
        step_index = 0
        due_time = now + dt.timedelta(minutes=relearning_steps[0])
        return due_time, "relearn", step_index, ease_factor
    
    if quality == 3:  # Good
        # Progress to next relearning step or graduate back to review
        if step_index + 1 < len(relearning_steps):
            step_index += 1
            due_time = now + dt.timedelta(minutes=relearning_steps[step_index])
            return due_time, "relearn", step_index, ease_factor
        else:
            # Graduate back to review with minimum interval
            min_interval = max(1, int(os.getenv("ANKI_MIN_INTERVAL_DAYS", "1")))
            due_time = now + dt.timedelta(days=min_interval)
            return due_time, "review", 0, ease_factor
    
    else:  # Easy (4)
        # Graduate back to review with easy interval
        due_time = now + dt.timedelta(days=DEFAULT_EASY_INTERVAL)
        return due_time, "review", 0, ease_factor


def review_card(now: dt.datetime, phase: str, interval_days: int, ease_factor: float, 
               step_index: int, quality: int) -> Tuple[dt.datetime, str, int, float, int]:
    """Main entry point for reviewing a card.
    
    Args:
        now: Current datetime
        phase: Current phase ("new", "learn", "review", "relearn")
        interval_days: Current interval in days
        ease_factor: Current ease factor
        step_index: Current step index for learning/relearning
        quality: Quality rating (0-4)
    
    Returns:
        (due_time, new_phase, new_step_index, new_ease_factor, new_interval_days)
    """
    now = now.astimezone(TZ)
    ease_factor = ease_factor or DEFAULT_EASE_FACTOR
    
    if phase == "new":
        due_time, new_phase, new_step_index, new_ease_factor = schedule_new_card(now, quality, step_index)
        new_interval_days = DEFAULT_GRADUATING_INTERVAL if new_phase == "review" else 0
        return due_time, new_phase, new_step_index, new_ease_factor, new_interval_days
    
    elif phase == "learn":
        due_time, new_phase, new_step_index, new_ease_factor = schedule_learning_card(now, quality, step_index, ease_factor)
        new_interval_days = DEFAULT_GRADUATING_INTERVAL if new_phase == "review" else 0
        return due_time, new_phase, new_step_index, new_ease_factor, new_interval_days
    
    elif phase == "review":
        due_time, new_phase, new_step_index, new_ease_factor, new_interval_days = schedule_review_card(
            now, quality, interval_days, ease_factor
        )
        return due_time, new_phase, new_step_index, new_ease_factor, new_interval_days
    
    elif phase == "relearn":
        due_time, new_phase, new_step_index, new_ease_factor = schedule_relearning_card(now, quality, step_index, ease_factor)
        new_interval_days = 1 if new_phase == "review" else 0
        return due_time, new_phase, new_step_index, new_ease_factor, new_interval_days
    
    else:
        # Fallback for unknown phase
        raise ValueError(f"Unknown phase: {phase}")
