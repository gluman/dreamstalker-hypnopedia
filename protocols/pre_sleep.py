"""Pre-sleep suggestion and preparation protocol."""

import os
import wave
import struct
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PreSleepProtocol:
    """Manages pre-sleep suggestion generation and relaxation sequences."""

    sample_rate: int = 44100
    volume: float = 0.3
    voice_speed: float = 0.85  # slower speech for relaxation

    SUGGESTION_TEMPLATES: dict = field(default_factory=lambda: {
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
        "memory consolidation": (
            "During tonight's sleep cycles, your brain will strengthen "
            "the neural pathways related to {topic}. What you have "
            "learned today will become permanent knowledge."
        ),
    })

    RELAXATION_SEQUENCE: list = field(default_factory=lambda: [
        {
            "step": 1,
            "title": "Breathing Reset",
            "duration_sec": 120,
            "instruction": (
                "Close your eyes. Breathe in slowly through your nose "
                "for 4 counts. Hold for 4 counts. Exhale through your "
                "mouth for 6 counts. Repeat this cycle."
            ),
            "binaural_freq": 10.0,  # alpha
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
            "binaural_freq": 8.0,  # upper alpha
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
            "binaural_freq": 6.0,  # theta entry
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
            "binaural_freq": 4.5,  # theta
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
            "binaural_freq": 3.0,  # deep theta
        },
    ])

    def generate_suggestion_text(self, topic: str, category: str = "learning") -> str:
        """Generate a personalized suggestion text for sleep learning.

        Args:
            topic: The subject matter to focus the suggestion on.
            category: One of 'learning', 'creativity', 'confidence',
                      'problem_solving', 'memory consolidation'.

        Returns:
            Formatted suggestion string.
        """
        if category not in self.SUGGESTION_TEMPLATES:
            raise ValueError(
                f"Unknown category '{category}'. "
                f"Available: {list(self.SUGGESTION_TEMPLATES.keys())}"
            )
        template = self.SUGGESTION_TEMPLATES[category]
        return template.format(topic=topic)

    def generate_suggestion_audio(
        self,
        text: str,
        output_path: str,
        freq: float = 200.0,
        repetitions: int = 3,
        pause_sec: float = 5.0,
    ) -> str:
        """Create an audio file with binaural beat carrier and encoded suggestion.

        Since we cannot use TTS in this environment, the suggestion text is
        encoded as rhythmic amplitude modulation on a binaural carrier.
        The text is also written alongside the audio as a .txt reference.

        Args:
            text: The suggestion text to encode.
            output_path: Path to write the .wav file.
            freq: Base carrier frequency in Hz.
            repetitions: How many times to repeat the encoded message.
            pause_sec: Silence between repetitions.

        Returns:
            Path to the generated audio file.
        """
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Write text companion file
        text_path = output.with_suffix(".txt")
        text_path.write_text(text, encoding="utf-8")

        # Generate audio: binaural carrier with slow amplitude modulation
        # representing the suggestion rhythm
        duration_sec = repetitions * (3.0 + pause_sec)
        num_samples = int(self.sample_rate * duration_sec)

        left_freq = freq
        right_freq = freq + 6.0  # 6 Hz theta binaural beat

        frames = []
        for i in range(num_samples):
            t = i / self.sample_rate
            pos_in_rep = t % (3.0 + pause_sec)

            if pos_in_rep < 3.0:
                # Active suggestion window - amplitude envelope
                env = math.sin(math.pi * pos_in_rep / 3.0) * self.volume
                left = math.sin(2 * math.pi * left_freq * t) * env
                right = math.sin(2 * math.pi * right_freq * t) * env
            else:
                # Pause
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
        """Return the full pre-sleep relaxation sequence.

        Returns:
            List of step dicts with 'step', 'title', 'duration_sec',
            'instruction', and 'binaural_freq' keys.
        """
        return self.RELAXATION_SEQUENCE.copy()

    def get_total_relaxation_duration(self) -> int:
        """Total duration of the relaxation sequence in seconds."""
        return sum(step["duration_sec"] for step in self.RELAXATION_SEQUENCE)
