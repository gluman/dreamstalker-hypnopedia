import numpy as np
from scipy.io import wavfile


def get_anchor_freq(index: int, base: float = 800.0) -> float:
    return base + index * 100.0


class AnchorGenerator:
    def __init__(self, sample_rate=44100, base_freq=800.0, duration=0.5):
        self.sample_rate = sample_rate
        self.base_freq = base_freq
        self.duration = duration

    def generate_anchor(self, index: int) -> np.ndarray:
        freq = get_anchor_freq(index, self.base_freq)
        n_samples = int(self.sample_rate * self.duration)
        t = np.linspace(0, self.duration, n_samples, endpoint=False)

        fundamental = np.sin(2 * np.pi * freq * t)
        fifth = 0.5 * np.sin(2 * np.pi * freq * 1.5 * t)
        octave = 0.3 * np.sin(2 * np.pi * freq * 2.0 * t)

        tone = fundamental + fifth + octave
        envelope = np.hanning(n_samples)
        tone *= envelope * 0.3

        return tone

    def generate_anchor_sequence(self, indices: list) -> np.ndarray:
        gap_samples = int(self.sample_rate * 0.3)
        gap = np.zeros(gap_samples)

        parts = []
        for i, idx in enumerate(indices):
            parts.append(self.generate_anchor(idx))
            if i < len(indices) - 1:
                parts.append(gap)

        return np.concatenate(parts)

    def assign_anchors(self, items: list) -> list:
        for i, item in enumerate(items):
            item["anchor_index"] = i
            item["anchor_freq"] = get_anchor_freq(i, self.base_freq)
        return items

    def create_decoder_track(self, items: list, speech_fn=None) -> np.ndarray:
        gap_samples = int(self.sample_rate * 0.3)
        gap = np.zeros(gap_samples)

        parts = []
        for item in items:
            anchor = self.generate_anchor(item.get("anchor_index", items.index(item)))
            for rep in range(3):
                parts.append(anchor)
                parts.append(gap)
                if speech_fn is not None:
                    speech_audio = speech_fn(item)
                    if isinstance(speech_audio, np.ndarray):
                        parts.append(speech_audio)
                        parts.append(gap)

        if not parts:
            return np.zeros(0, dtype=np.float64)
        return np.concatenate(parts)

    def create_decoder_wav(self, items: list, output_path: str, speech_fn=None) -> str:
        audio = self.create_decoder_track(items, speech_fn=speech_fn)
        audio_16 = np.int16(audio * 32767)
        wavfile.write(output_path, self.sample_rate, audio_16)
        return output_path
