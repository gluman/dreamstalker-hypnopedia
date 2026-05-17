#!/usr/bin/env python3
"""
Matrix Download Generator — Chinese Language
Generates a single 7-hour WAV file chunk-by-chunk to avoid memory issues.
All learning content encoded via steganography, anchors, binaural beats, TMR cues.
"""

import json
import wave
import struct
import numpy as np
from pathlib import Path
from scipy.io import wavfile
from scipy import signal as scipy_signal

from core.binaural import generate_sweep
from core.steganography import encode as stego_encode, StegoConfig, StegoMethod
from core.anchor_generator import AnchorGenerator


def build_stego_text(pkg: dict) -> str:
    """Combine all learning content into a single text string for steganographic encoding."""
    parts = []
    parts.append("TONES: " + " | ".join(pkg["phonetics"]))
    parts.append("INITIALS: " + " | ".join(pkg["pinyin_initials"]))
    parts.append("FINALS: " + " | ".join(pkg["pinyin_finals"]))

    word_lines = []
    for w in pkg["core_words_300"]:
        word_lines.append(f"{w['cn']} {w['py']} {w['ru']}")
    parts.append("WORDS: " + " | ".join(word_lines))

    parts.append("GRAMMAR: " + " | ".join(pkg["grammar_patterns"]))

    dialogue_lines = []
    for d in pkg["dialogue_templates"]:
        dialogue_lines.append(f"{d['ru']} | {d['cn']} | {d['py']}")
    parts.append("DIALOGUES: " + " | ".join(dialogue_lines))

    parts.append("AFFIRMATIONS: " + " | ".join(pkg["os_affirmations"]))
    parts.append("TRIGGERS: " + " | ".join(pkg["os_triggers"]))

    return " ||| ".join(parts)


def generate_pink_noise(duration_sec: float, sr: int, amplitude: float = 0.12) -> np.ndarray:
    n = int(sr * duration_sec)
    white = np.random.randn(n)
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
    a = [1.0, -2.494956002, 2.017265875, -0.522189400]
    pink = scipy_signal.lfilter(b, a, white)
    pink = pink / np.max(np.abs(pink))
    return pink * amplitude


def generate_wind(duration_sec: float, sr: int, volume: float = 0.06) -> np.ndarray:
    n = int(sr * duration_sec)
    t = np.arange(n) / sr
    base = np.random.randn(n)
    sos = scipy_signal.butter(4, [80, 400], btype='band', fs=sr, output='sos')
    filtered = scipy_signal.sosfilt(sos, base)
    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.15 * t)
    return filtered * mod * volume


def generate_cricket_chirps(duration_sec: float, sr: int, volume: float = 0.06) -> np.ndarray:
    n = int(sr * duration_sec)
    out = np.zeros(n)
    chirp_len = int(0.02 * sr)
    env = np.hanning(chirp_len)
    interval = int(sr / 12.0)
    t = np.arange(chirp_len) / sr
    chirp = np.sin(2 * np.pi * 4500 * t) * env
    for pos in range(0, n - chirp_len, interval):
        jitter = np.random.randint(-interval // 4, interval // 4)
        start = max(0, pos + jitter)
        end = min(n, start + chirp_len)
        length = end - start
        out[start:end] += chirp[:length] * 0.5
    return out * volume


def generate_binaural_chunk(start_freq: float, end_freq: float, duration: float,
                            sr: int, base_freq: float = 200.0, volume: float = 0.25) -> np.ndarray:
    """Generate binaural sweep for a chunk (stereo)."""
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    freq = start_freq * (end_freq / start_freq) ** (t / duration)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    left = volume * np.sin(2 * np.pi * base_freq * t)
    right = volume * np.sin(2 * np.pi * base_freq * t + phase)
    return np.array([left, right])


def generate_tmr_cue(duration: float = 0.5, freq: float = 1000.0,
                     volume: float = 0.10, sr: int = 44100) -> np.ndarray:
    n = int(sr * duration)
    t = np.arange(n) / sr
    tone = np.sin(2 * np.pi * freq * t)
    tone *= np.sin(2 * np.pi * freq * 1.5 * t) * 0.3
    fade = int(sr * 0.05)
    env = np.ones(n)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    return tone * env * volume


def generate_anchor_tone(index: int, base_freq: float = 800.0,
                         duration: float = 0.5, sr: int = 44100) -> np.ndarray:
    freq = base_freq + index * 100.0
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    tone = np.sin(2 * np.pi * freq * t)
    tone += 0.5 * np.sin(2 * np.pi * freq * 1.5 * t)
    tone += 0.3 * np.sin(2 * np.pi * freq * 2.0 * t)
    tone *= np.hanning(n) * 0.3
    return tone


def generate_gamma_burst(duration: float = 2.0, freq: float = 40.0,
                         base: float = 200.0, volume: float = 0.15, sr: int = 44100) -> np.ndarray:
    """Gamma burst for lucid dream triggering."""
    n = int(sr * duration)
    t = np.arange(n) / sr
    left = volume * np.sin(2 * np.pi * base * t)
    right = volume * np.sin(2 * np.pi * (base + freq) * t)
    env = np.hanning(n)
    return np.array([left * env, right * env])


def encode_stego_chunk(carrier: np.ndarray, text: str, sr: int) -> np.ndarray:
    """Encode text into carrier audio using phase encoding."""
    cfg = StegoConfig(method=StegoMethod.PHASE_ENCODING, sample_rate=sr)
    return stego_encode(carrier, text, cfg)


def generate_matrix_audio(
    pkg_path: str = "data/chinese/matrix/core_package.json",
    output_path: str = "data/chinese/matrix/matrix_download.wav",
    hours: float = 7.0,
    sample_rate: int = 44100,
    chunk_minutes: float = 5.0,
):
    """Generate the full matrix download audio file chunk-by-chunk."""
    print(f"Loading package: {pkg_path}")
    with open(pkg_path, encoding="utf-8") as f:
        pkg = json.load(f)

    word_count = len(pkg["core_words_300"])
    print(f"Package: {word_count} words, {len(pkg['grammar_patterns'])} grammar, {len(pkg['dialogue_templates'])} dialogues")

    stego_text = build_stego_text(pkg)
    print(f"Stego text: {len(stego_text)} chars")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    chunk_sec = int(chunk_minutes * 60)
    total_sec = int(hours * 3600)
    n_chunks = (total_sec + chunk_sec - 1) // chunk_sec

    sr = sample_rate
    print(f"Generating {hours}h audio in {n_chunks} chunks ({chunk_minutes} min each)...")

    # Pre-generate stego-encoded carrier for the full text (short version)
    # We'll encode the text into a carrier that repeats throughout
    stego_carrier_len = int(sr * chunk_sec)
    stego_carrier = np.random.randn(stego_carrier_len).astype(np.float32) * 0.005
    print("Encoding steganographic text into carrier...")
    stego_audio = encode_stego_chunk(stego_carrier, stego_text, sr)
    if stego_audio.ndim == 2:
        stego_audio = stego_audio.mean(axis=0)

    # Pre-generate anchor sequence
    anchor_gen = AnchorGenerator(sample_rate=sr)
    anchor_cycle = []
    for w in pkg["core_words_300"]:
        idx = int((w["anchor_hz"] - 800) / 10)
        anchor_cycle.append(generate_anchor_tone(idx, sr=sr))
        anchor_cycle.append(np.zeros(int(sr * 0.3)))
    anchor_full = np.concatenate(anchor_cycle)
    anchor_len = len(anchor_full)
    print(f"Anchor sequence: {anchor_len / sr:.1f}s for {word_count} words")

    # Pre-generate TMR cues
    tmr_interval = 300  # every 5 min
    tmr_cue = generate_tmr_cue(sr=sr)
    tmr_cue_len = len(tmr_cue)

    # Pre-generate gamma bursts (for REM phases)
    gamma = generate_gamma_burst(sr=sr)
    gamma_len = gamma.shape[1]

    with wave.open(str(output), 'w') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sr)

        for chunk_idx in range(n_chunks):
            chunk_start = chunk_idx * chunk_sec
            chunk_end = min(chunk_start + chunk_sec, total_sec)
            chunk_dur = chunk_end - chunk_start
            if chunk_dur <= 0:
                break

            progress = chunk_start / total_sec * 100
            print(f"  Chunk {chunk_idx + 1}/{n_chunks} ({progress:.0f}%) — {chunk_start // 60}min")

            n = int(sr * chunk_dur)
            track = np.zeros(n, dtype=np.float64)

            # Phase determination
            min_in = chunk_start / 60.0
            if min_in < 30:
                # Alpha phase (0-30 min): relaxation
                binaural = generate_binaural_chunk(14.0, 10.0, chunk_dur, sr, volume=0.2)
                if binaural.ndim == 2:
                    binaural = binaural.mean(axis=0)
                track += binaural[:n] * 0.2
            elif min_in < 150:
                # Theta phase (30-150 min): dream transition
                binaural = generate_binaural_chunk(10.0, 5.0, chunk_dur, sr, volume=0.2)
                if binaural.ndim == 2:
                    binaural = binaural.mean(axis=0)
                track += binaural[:n] * 0.2
            elif min_in < 360:
                # Delta phase (150-360 min): deep sleep, consolidation
                binaural = generate_binaural_chunk(5.0, 2.0, chunk_dur, sr, volume=0.15)
                if binaural.ndim == 2:
                    binaural = binaural.mean(axis=0)
                track += binaural[:n] * 0.15
            elif min_in < 420:
                # REM phase (360-420 min): lucid dreaming triggers
                binaural = generate_binaural_chunk(2.0, 5.0, chunk_dur, sr, volume=0.2)
                if binaural.ndim == 2:
                    binaural = binaural.mean(axis=0)
                track += binaural[:n] * 0.2
                # Add gamma bursts every 2 min
                pos = 0
                while pos < n - gamma_len:
                    g_mono = gamma.mean(axis=0)
                    track[pos:pos + gamma_len] += g_mono * 0.1
                    pos += int(120 * sr)
            else:
                # Wake-up phase (420-480 min): return to alpha
                binaural = generate_binaural_chunk(5.0, 10.0, chunk_dur, sr, volume=0.2)
                if binaural.ndim == 2:
                    binaural = binaural.mean(axis=0)
                track += binaural[:n] * 0.2

            # Ambient layer
            ambient_dur = min(chunk_dur, 60.0)  # generate 60s ambient, loop
            pink = generate_pink_noise(ambient_dur, sr, 0.10)
            wind = generate_wind(ambient_dur, sr, 0.05)
            crickets = generate_cricket_chirps(ambient_dur, sr, 0.04)
            ambient = pink + wind + crickets
            # Loop ambient to fill chunk
            ambient_loop = np.tile(ambient, int(n / len(ambient)) + 1)[:n]
            track += ambient_loop * 0.3

            # Steganography layer (repeat encoded text)
            stego_loop = np.tile(stego_audio, int(n / len(stego_audio)) + 1)[:n]
            track += stego_loop * 0.03

            # Anchor tones layer (cycle through all 300 words)
            anchor_loop = np.tile(anchor_full, int(n / anchor_len) + 1)[:n]
            track += anchor_loop * 0.08

            # TMR cues every 5 min
            if chunk_idx > 0:
                tmr_pos = 0
                while tmr_pos < n - tmr_cue_len:
                    track[tmr_pos:tmr_pos + tmr_cue_len] += tmr_cue * 0.1
                    tmr_pos += tmr_interval * sr

            # Clip and write
            track = np.clip(track, -1.0, 1.0)
            track_int = (track * 32767).astype(np.int16)
            wav.writeframes(track_int.tobytes())

            # Free memory
            del track, track_int

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"\nAudio generated: {output}")
    print(f"Size: {size_mb:.1f} MB")
    print(f"Duration: {hours} hours")
    print(f"Sample rate: {sr} Hz")
    print(f"Words encoded: {word_count}")
    print(f"Grammar patterns: {len(pkg['grammar_patterns'])}")
    print(f"Dialogues: {len(pkg['dialogue_templates'])}")
    print(f"\nReady for sleep session. Stereo headphones, low volume.")


if __name__ == "__main__":
    generate_matrix_audio()
