# -*- coding: utf-8 -*-
from enum import Enum
from typing import List

class Technique(Enum):
    WILD = "wild"
    MILD = "mild"
    SSILD = "ssild"
    FILD = "fild"

WILD_STEPS = [
    "1. Lie on your back, arms at sides, completely still",
    "2. Focus on hypnagogia (patterns behind closed eyes)",
    "3. Do not move or swallow - ignore itching",
    "4. Wait for sleep paralysis / vibrations",
    "5. When vibrations start, intensify them with will",
    "6. Visualize yourself rolling out of body",
    "7. Stand up in the dream environment",
    "8. Perform a reality check",
]

MILD_STEPS = [
    "1. Wake up after 4-6 hours of sleep",
    "2. Recall your last dream in detail",
    "3. Identify a dream sign",
    "4. Repeat: Next time I dream I will realize I am dreaming",
    "5. Visualize yourself becoming lucid",
    "6. Visualize what you will do when lucid",
    "7. Fall back asleep with this intention",
]

SSILD_STEPS = [
    "1. Wake up after 4-6 hours",
    "2. 5 cycles: sight(10s) sound(10s) touch(10s)",
    "3. 5 cycles: sight(5s) sound(5s) touch(5s)",
    "4. 5 cycles: sight(3s) sound(3s) touch(3s)",
    "5. Let go and fall asleep naturally",
]

STEPS = {Technique.WILD: WILD_STEPS, Technique.MILD: MILD_STEPS, Technique.SSILD: SSILD_STEPS, Technique.FILD: MILD_STEPS}

class LucidDreamProtocol:
    def get_instructions(self, technique: Technique) -> List[str]:
        return STEPS.get(technique, MILD_STEPS)
    def get_full_protocol(self, technique: Technique = Technique.MILD) -> str:
        return f"=== {technique.value.upper()} ===
" + chr(10).join(self.get_instructions(technique))
    def get_pre_sleep_affirmations(self) -> List[str]:
        return ["Tonight I will realize I am dreaming", "I am aware of my dreams", "I remember my dreams clearly"]
