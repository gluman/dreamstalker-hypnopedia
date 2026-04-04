# -*- coding: utf-8 -*-
from typing import List

RADUGA_STEPS = [
    "Phase 1 - Falling Asleep",
    "1. Set alarm for 4-6 hours after bedtime",
    "2. Upon waking stay still - do not open eyes",
    "3. Stay awake 3-5 min then lie on back",
    "Phase 2 - Separation",
    "4. Try to separate: roll out / float up / swim out / jump",
    "5. If paralyzed - separation is easier",
    "Phase 3 - Deepening",
    "6. Rub hands together to stabilize",
    "7. Look at hands examine details",
    "8. Touch objects feel textures",
    "9. Demand: CLEARER NOW!",
    "Phase 4 - Exploration",
    "10. Set a goal before each attempt",
    "11. Maintain awareness",
    "12. Return by thinking about body",
]

VIBRATION_GUIDE = """
The Vibration Stage: buzzing, tingling, rushing sounds.
Do NOT panic. Relax deeper. Intensify by focusing will.
When vibrations peak - separate immediately.
"""

class OBEProtocol:
    def get_raduga_method(self) -> List[str]:
        return RADUGA_STEPS.copy()
    def get_vibration_stage_guide(self) -> str:
        return VIBRATION_GUIDE
    def get_full_protocol(self) -> str:
        return chr(10).join(RADUGA_STEPS)
    def get_pre_obe_affirmations(self) -> List[str]:
        return ["I will separate from my body tonight", "The vibrations are safe", "I am more than my physical body"]
