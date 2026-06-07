"""Pre-sleep suggestion and preparation protocol.

This module is a thin wrapper around protocols/affirmations.py for backward
compatibility. New code should import from protocols.affirmations directly.
"""

import wave
import struct
import math
from pathlib import Path
from typing import Optional

from protocols.affirmations import (
    SUGGESTION_TEMPLATES,
    RELAXATION_SEQUENCE,
    get_suggestion as _get_suggestion,
    get_relaxation_sequence as _get_relaxation,
    get_total_relaxation_duration as _get_total_duration,
)


class PreSleepProtocol:
    """Manages pre-sleep suggestion generation and relaxation sequences."""

    SUGGESTION_TEMPLATES = SUGGESTION_TEMPLATES
    RELAXATION_SEQUENCE = RELAXATION_SEQUENCE

    def __init__(self, sample_rate: int = 44100, volume: float = 0.3,
                 voice_speed: float = 0.85):
        self.sample_rate = sample_rate
        self.volume = volume
        self.voice_speed = voice_speed

    def generate_suggestion_text(self, topic: str, category: str = "learning") -> str:
        """Generate a personalized suggestion text for sleep learning."""
        return _get_suggestion(topic, category)

    def generate_suggestion_audio(
        self,
        text: str,
        output_path: str,
        freq: float = 200.0,
        repetitions: int = 3,
        pause_sec: float = 5.0,
    ) -> str:
        """Create an audio file with binaural carrier and encoded suggestion."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        text_path = output.with_suffix(".txt")
        text_path.write_text(text, encoding="utf-8")

        duration_sec = repetitions * (3.0 + pause_sec)
        num_samples = int(self.sample_rate * duration_sec)
        left_freq = freq
        right_freq = freq + 6.0
        frames = []
        for i in range(num_samples):
            t = i / self.sample_rate
            pos_in_rep = t % (3.0 + pause_sec)
            if pos_in_rep < 3.0:
                env = math.sin(math.pi * pos_in_rep / 3.0) * self.volume
                left = math.sin(2 * math.pi * left_freq * t) * env
                right = math.sin(2 * math.pi * right_freq * t) * env
            else:
                left = 0.0
                right = 0.0
            frames.append(struct.pack('<hh', int(left * 32767), int(right * 32767)))

        with wave.open(str(output), 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(b''.join(frames))
        return str(output)

    def get_relaxation_sequence(self) -> list[dict]:
        return _get_relaxation()

    def get_total_relaxation_duration(self) -> int:
        return _get_total_duration()
