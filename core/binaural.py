"""
Binaural beats generator for sleep phase entrainment.

Generates binaural beats that progress through frequency ranges
corresponding to different sleep phases:
- Theta (4-7 Hz): REM sleep, dreaming
- Delta (0.5-4 Hz): Deep sleep (SWS)

Can also generate isochronic tones (no headphones required).
"""

import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class WaveType(Enum):
    BINAURAL = "binaural"       # Requires headphones
    ISOCHRONIC = "isochronic"   # Can use speakers
    MONAURAL = "monaural"       # Single carrier, no headphones


class SleepPhase(Enum):
    WAKE = "wake"
    ALPHA = "alpha"             # 8-12 Hz - relaxation
    THETA = "theta"             # 4-7 Hz - REM / dreaming
    DELTA = "delta"             # 0.5-4 Hz - deep sleep
    GAMMA = "gamma"             # 30-100 Hz - lucid dreaming / OBE


@dataclass
class BinauralConfig:
    base_frequency: float = 200.0       # Carrier frequency (Hz)
    target_frequency: float = 4.0       # Binaural beat frequency (Hz)
    duration: float = 3600.0            # Duration in seconds
    sample_rate: int = 44100            # Audio sample rate
    wave_type: WaveType = WaveType.BINAURAL
    volume: float = 0.3                 # 0.0 - 1.0


# Preset configurations for different sleep phases
PRESETS = {
    SleepPhase.WAKE: BinauralConfig(
        base_frequency=300.0,
        target_frequency=14.0,      # Beta waves
        wave_type=WaveType.BINAURAL,
    ),
    SleepPhase.ALPHA: BinauralConfig(
        base_frequency=250.0,
        target_frequency=10.0,      # Alpha waves
        wave_type=WaveType.BINAURAL,
    ),
    SleepPhase.THETA: BinauralConfig(
        base_frequency=200.0,
        target_frequency=5.0,       # Theta waves
        wave_type=WaveType.BINAURAL,
    ),
    SleepPhase.DELTA: BinauralConfig(
        base_frequency=150.0,
        target_frequency=2.0,       # Delta waves
        wave_type=WaveType.BINAURAL,
    ),
    SleepPhase.GAMMA: BinauralConfig(
        base_frequency=400.0,
        target_frequency=40.0,      # Gamma waves (lucid/OBE)
        wave_type=WaveType.BINAURAL,
    ),
}


def generate_binaural_beats(config: BinauralConfig) -> np.ndarray:
    """Generate binaural beats audio array.

    Returns stereo array with shape (2, n_samples) where
    left channel = base_frequency, right channel = base + target.
    """
    n_samples = int(config.sample_rate * config.duration)
    t = np.linspace(0, config.duration, n_samples, endpoint=False)

    left_freq = config.base_frequency
    right_freq = config.base_frequency + config.target_frequency

    if config.wave_type == WaveType.BINAURAL:
        left = config.volume * np.sin(2 * np.pi * left_freq * t)
        right = config.volume * np.sin(2 * np.pi * right_freq * t)
        return np.array([left, right])

    elif config.wave_type == WaveType.MONAURAL:
        # Monaural: mix both frequencies into one channel
        beat = config.volume * (
            np.sin(2 * np.pi * left_freq * t) +
            np.sin(2 * np.pi * right_freq * t)
        ) / 2
        return np.array([beat, beat])

    elif config.wave_type == WaveType.ISOCHRONIC:
        # Isochronic: pulsing tone at target frequency
        envelope = 0.5 * (1 + np.sign(np.sin(2 * np.pi * config.target_frequency * t)))
        tone = config.volume * np.sin(2 * np.pi * config.base_frequency * t) * envelope
        return np.array([tone, tone])


def generate_sweep(
    start_freq: float,
    end_freq: float,
    duration: float,
    sample_rate: int = 44100,
    base_freq: float = 200.0,
    volume: float = 0.3,
) -> np.ndarray:
    """Generate a frequency sweep (gradual change from start to end).

    Useful for transitioning between sleep phases during the night.
    """
    n_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    # Logarithmic frequency sweep
    freq = start_freq * (end_freq / start_freq) ** (t / duration)

    # Cumulative phase for smooth sweep
    phase = 2 * np.pi * np.cumsum(freq) / sample_rate

    left = volume * np.sin(2 * np.pi * base_freq * t)
    right = volume * np.sin(2 * np.pi * base_freq * t + phase)

    return np.array([left, right])


def generate_night_progression(
    total_hours: float = 8.0,
    sample_rate: int = 44100,
    base_freq: float = 200.0,
    volume: float = 0.3,
) -> np.ndarray:
    """Generate a full night's binaural beat progression.

    Phases:
    1. Wake -> Alpha (30 min): Relaxation and pre-sleep
    2. Alpha -> Theta (60 min): Transition to dreaming
    3. Theta cycles (remaining): Oscillate between theta and delta
       to match natural 90-minute sleep cycles
    """
    total_sec = total_hours * 3600
    segments = []

    # For short sessions (< 15 min), just do a simple sweep
    if total_sec < 900:
        segments.append(generate_sweep(
            start_freq=14.0, end_freq=4.0,
            duration=total_sec, sample_rate=sample_rate,
            base_freq=base_freq, volume=volume,
        ))
        return np.concatenate(segments, axis=1)

    # Phase 1: Wake to Alpha (min 30 min or 1/6 of total)
    phase1_sec = min(30 * 60, total_sec / 6)
    segments.append(generate_sweep(
        start_freq=14.0, end_freq=10.0,
        duration=phase1_sec, sample_rate=sample_rate,
        base_freq=base_freq, volume=volume,
    ))

    # Phase 2: Alpha to Theta (min 60 min or 1/3 of total)
    phase2_sec = min(60 * 60, total_sec / 3)
    segments.append(generate_sweep(
        start_freq=10.0, end_freq=5.0,
        duration=phase2_sec, sample_rate=sample_rate,
        base_freq=base_freq, volume=volume,
    ))

    # Phase 3: 90-minute sleep cycles (theta <-> delta)
    remaining_sec = total_sec - phase1_sec - phase2_sec
    cycle_sec = 90 * 60  # natural sleep cycle
    n_cycles = max(1, int(remaining_sec / cycle_sec))

    for i in range(n_cycles):
        rem_sec = min(20 * 60, remaining_sec / n_cycles * 0.22)
        deep_sec = remaining_sec / n_cycles - rem_sec
        if rem_sec > 0:
            segments.append(generate_binaural_beats(BinauralConfig(
                base_frequency=base_freq,
                target_frequency=5.0 + np.random.uniform(-0.5, 0.5),
                duration=rem_sec,
                sample_rate=sample_rate,
                volume=volume,
            )))
        if deep_sec > 0:
            segments.append(generate_binaural_beats(BinauralConfig(
                base_frequency=base_freq,
                target_frequency=2.0 + np.random.uniform(-0.3, 0.3),
                duration=deep_sec,
                sample_rate=sample_rate,
                volume=volume,
            )))

    return np.concatenate(segments, axis=1)


if __name__ == "__main__":
    # Quick test: generate 10 seconds of theta binaural beats
    config = PRESETS[SleepPhase.THETA]
    config.duration = 10.0
    audio = generate_binaural_beats(config)
    print(f"Generated {audio.shape[1]} samples at {config.sample_rate} Hz")
    print(f"Duration: {audio.shape[1] / config.sample_rate:.1f}s")
    print(f"Target freq: {config.target_frequency} Hz")
