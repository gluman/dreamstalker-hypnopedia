#!/usr/bin/env python3
"""
Matrix Download Generator — Chinese Language
Generates a single 7-hour WAV file using core/audio_generator.py (chunk-based).
All learning content encoded via steganography, anchors, binaural beats, TMR cues.
"""

import json
from pathlib import Path

from core.audio_generator import NightAudioGenerator, NightConfig, AmbientConfig, TMRConfig
from core.binaural import generate_sweep
from core.steganography import encode as stego_encode, StegoConfig, StegoMethod
from core.anchor_generator import AnchorGenerator


def build_stego_text(pkg: dict) -> str:
    """Combine all learning content into a single text string for steganographic encoding."""
    parts = []
    parts.append("TONES: " + " | ".join(pkg["phonetics"]))
    parts.append("INITIALS: " + " | ".join(pkg["pinyin_initials"]))
    parts.append("FINALS: " + " | ".join(pkg["pinyin_finals"]))

    word_lines = [f"{w['cn']} {w['py']} {w['ru']}" for w in pkg["core_words_300"]]
    parts.append("WORDS: " + " | ".join(word_lines))

    parts.append("GRAMMAR: " + " | ".join(pkg["grammar_patterns"]))

    dialogue_lines = [f"{d['ru']} | {d['cn']} | {d['py']}" for d in pkg["dialogue_templates"]]
    parts.append("DIALOGUES: " + " | ".join(dialogue_lines))

    parts.append("AFFIRMATIONS: " + " | ".join(pkg["os_affirmations"]))
    parts.append("TRIGGERS: " + " | ".join(pkg["os_triggers"]))

    return " ||| ".join(parts)


def inject_anchor_layer(wav_path: str, pkg: dict, sample_rate: int = 44100):
    """Overlay anchor tones on top of the generated night audio (post-processing)."""
    from scipy.io import wavfile
    import numpy as np

    print("Injecting anchor layer...")
    sr, audio = wavfile.read(wav_path)
    audio = audio.astype(np.float32) / 32767.0
    n = len(audio)

    anchor_gen = AnchorGenerator(sample_rate=sr)
    cycle_parts = []
    for w in pkg["core_words_300"]:
        idx = int((w["anchor_hz"] - 800) / 10)
        cycle_parts.append(anchor_gen.generate_anchor(idx))
        cycle_parts.append(np.zeros(int(sr * 0.3)))
    cycle = np.concatenate(cycle_parts)
    if len(cycle) == 0:
        return

    full = np.resize(cycle, n).astype(np.float32)
    mixed = audio + full * 0.05
    mixed = np.clip(mixed, -1.0, 1.0)
    mixed_int = (mixed * 32767).astype(np.int16)
    wavfile.write(wav_path, sr, mixed_int)
    print(f"Anchor layer added ({len(pkg['core_words_300'])} tones)")


def generate_matrix_audio(
    pkg_path: str = "data/chinese/matrix/core_package.json",
    output_path: str = "data/chinese/matrix/matrix_download.wav",
    hours: float = 7.0,
    sample_rate: int = 44100,
):
    """Generate the full matrix download audio file using core's chunk-based engine."""
    print(f"Loading package: {pkg_path}")
    with open(pkg_path, encoding="utf-8") as f:
        pkg = json.load(f)

    word_count = len(pkg["core_words_300"])
    print(f"Package: {word_count} words, {len(pkg['grammar_patterns'])} grammar, "
          f"{len(pkg['dialogue_templates'])} dialogues")

    stego_text = build_stego_text(pkg)
    print(f"Stego text: {len(stego_text)} chars")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    night_cfg = NightConfig(
        sample_rate=sample_rate,
        ambient=AmbientConfig(pink_noise_amplitude=0.10, nature_volume=0.05),
        tmr=TMRConfig(cue_duration=0.5, cue_freq=1000.0, cue_volume=0.08,
                      min_interval=300.0, max_interval=600.0),
    )
    gen = NightAudioGenerator(night_cfg)

    print(f"Generating {hours}h audio (chunk-based, memory-safe)...")
    gen.generate_full_night(
        hours=hours,
        knowledge_items=[stego_text],
        output_path=str(output),
        chunk_minutes=5.0,
    )

    inject_anchor_layer(str(output), pkg, sample_rate)

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"\nAudio generated: {output}")
    print(f"Size: {size_mb:.1f} MB | Duration: {hours}h | Sample rate: {sample_rate}Hz")
    print(f"Words: {word_count} | Grammar: {len(pkg['grammar_patterns'])} "
          f"| Dialogues: {len(pkg['dialogue_templates'])}")
    print("\nReady for sleep session. Stereo headphones, low volume.")


if __name__ == "__main__":
    generate_matrix_audio()
