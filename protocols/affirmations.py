"""Single source of truth for affirmations, suggestions, and relaxation prompts.

Replaces scattered templates from protocols/pre_sleep.py and core_package.json.
All audio generators, web UIs, and CLI tools should import from here.
"""

from typing import Dict, List

# --- Suggestion templates (replaces protocols/pre_sleep.py templates) -----

SUGGESTION_TEMPLATES: Dict[str, str] = {
    "learning": (
        "Tonight, your mind will absorb and retain the knowledge "
        "presented during your sleep. Each concept will settle deeply "
        "into your long-term memory. You will awaken with a clear "
        "understanding of {topic}."
    ),
    "creativity": (
        "As you sleep, your subconscious mind will explore creative "
        "solutions related to {topic}. New ideas will emerge naturally "
        "and you will remember them upon waking."
    ),
    "confidence": (
        "You are capable and strong. Tonight's rest will reinforce "
        "your confidence regarding {topic}. You will wake feeling "
        "prepared and self-assured."
    ),
    "problem_solving": (
        "Your mind will work through the challenges of {topic} "
        "while you sleep. The solution will become clear to you "
        "by morning. Trust your subconscious process."
    ),
    "memory_consolidation": (
        "During tonight's sleep cycles, your brain will strengthen "
        "the neural pathways related to {topic}. What you have "
        "learned today will become permanent knowledge."
    ),
}

# --- Pre-sleep relaxation sequence ----------------------------------------

RELAXATION_SEQUENCE: List[dict] = [
    {
        "step": 1,
        "title": "Breathing Reset",
        "duration_sec": 120,
        "instruction": (
            "Close your eyes. Breathe in slowly through your nose "
            "for 4 counts. Hold for 4 counts. Exhale through your "
            "mouth for 6 counts. Repeat this cycle."
        ),
        "binaural_freq": 10.0,
    },
    {
        "step": 2,
        "title": "Progressive Muscle Relaxation",
        "duration_sec": 300,
        "instruction": (
            "Starting with your toes, tense each muscle group for "
            "5 seconds, then release. Move upward: feet, calves, "
            "thighs, abdomen, chest, hands, arms, shoulders, neck, face. "
            "Feel the tension dissolve with each release."
        ),
        "binaural_freq": 8.0,
    },
    {
        "step": 3,
        "title": "Body Scan",
        "duration_sec": 240,
        "instruction": (
            "Bring your awareness to the top of your head. Slowly "
            "scan downward through your body. Notice any remaining "
            "tension and let it go. Your body is becoming heavy "
            "and deeply relaxed."
        ),
        "binaural_freq": 6.0,
    },
    {
        "step": 4,
        "title": "Visualization",
        "duration_sec": 300,
        "instruction": (
            "Imagine yourself at the top of a staircase with "
            "10 steps. With each step down, you sink deeper into "
            "relaxation. Count backward from 10. At the bottom, "
            "you find a peaceful place. Explore it with all "
            "your senses."
        ),
        "binaural_freq": 4.5,
    },
    {
        "step": 5,
        "title": "Intention Setting",
        "duration_sec": 120,
        "instruction": (
            "Set your intention for tonight's sleep. Repeat silently: "
            "'I will remain aware as I fall asleep. I will remember "
            "my dreams. I will recognize when I am dreaming.' "
            "Let this intention anchor as you drift off."
        ),
        "binaural_freq": 3.0,
    },
]

# --- Lucid dream affirmations (replaces core_package.json os_affirmations) -

LUCID_AFFIRMATIONS: List[str] = [
    "Tonight I will realize I am dreaming",
    "I am aware of my dreams",
    "I remember my dreams clearly",
    "When I see something strange, I will do a reality check",
    "I recognize dream signs and become lucid",
    "I am in control of my dreams",
    "My subconscious mind guides me to lucidity",
    "I wake up refreshed and remember my lucid dreams",
]

# --- Lucid dream reality-check triggers (replaces core_package.json) -------

LUCID_TRIGGERS: List[str] = [
    "Look at your hands — count the fingers. If you can't, you're dreaming.",
    "Try to read text twice. If it changes, you're dreaming.",
    "Pinch your nose and try to breathe through it. If you can, you're dreaming.",
    "Look at a clock, look away, look back. If time changed, you're dreaming.",
    "Push your finger through your palm. If it goes through, you're dreaming.",
]

# --- Helper API ------------------------------------------------------------

def get_suggestion(topic: str, category: str = "learning") -> str:
    """Format a suggestion for the given topic and category."""
    if category not in SUGGESTION_TEMPLATES:
        raise ValueError(
            f"Unknown category '{category}'. "
            f"Available: {list(SUGGESTION_TEMPLATES.keys())}"
        )
    return SUGGESTION_TEMPLATES[category].format(topic=topic)


def get_lucid_bundle() -> dict:
    """Return the full lucid-dreaming bundle (affirmations + triggers)."""
    return {
        "affirmations": LUCID_AFFIRMATIONS,
        "triggers": LUCID_TRIGGERS,
    }


def get_relaxation_sequence() -> List[dict]:
    return RELAXATION_SEQUENCE.copy()


def get_total_relaxation_duration() -> int:
    return sum(step["duration_sec"] for step in RELAXATION_SEQUENCE)
