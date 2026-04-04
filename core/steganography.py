# -*- coding: utf-8 -*-
"""Audio steganography — encoding/decoding data within audio signals."""

import numpy as np
from scipy import signal as scipy_signal
from dataclasses import dataclass
from enum import Enum


class StegoMethod(Enum):
    LSB = "lsb"
    PHASE_ENCODING = "phase"
    SPREAD_SPECTRUM = "spread"


@dataclass
class StegoConfig:
    method: StegoMethod = StegoMethod.PHASE_ENCODING
    carrier_freq: float = 16000.0
    bits_per_sample: int = 2
    spread_factor: int = 8
    sample_rate: int = 44100


def text_to_bits(text):
    data = text.encode("utf-8")
    bits = []
    for byte in data:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    return np.array(bits, dtype=np.uint8)


def bits_to_text(bits):
    pad_len = (8 - len(bits) % 8) % 8
    bits = np.concatenate([bits, np.zeros(pad_len, dtype=np.uint8)])
    bytes_data = []
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | int(bits[i + j])
        bytes_data.append(byte)
    return bytes(bytes_data).decode("utf-8", errors="replace")


def _add_header(data_bits):
    length = len(data_bits)
    header = np.array([(length >> i) & 1 for i in range(31, -1, -1)], dtype=np.uint8)
    return np.concatenate([header, data_bits])


def encode_lsb(audio, text, config):
    data_bits = _add_header(text_to_bits(text))
    audio_int = (audio * 32767).astype(np.int32)
    flat = audio_int.flatten().copy()
    mask = ~((1 << config.bits_per_sample) - 1)
    if len(data_bits) > len(flat) * config.bits_per_sample:
        raise ValueError("Audio too short")
    bit_idx = 0
    for i in range(len(flat)):
        if bit_idx >= len(data_bits):
            break
        packed = 0
        for b in range(config.bits_per_sample):
            if bit_idx < len(data_bits):
                packed |= (int(data_bits[bit_idx]) << (config.bits_per_sample - 1 - b))
                bit_idx += 1
        val = (int(flat[i]) & mask) | packed
        flat[i] = max(-32767, min(32767, val))
    return flat.reshape(audio.shape).astype(np.float32) / 32767.0


def decode_lsb(audio, config):
    audio_int = (audio * 32767).astype(np.int32)
    flat = audio_int.flatten()
    all_bits = []
    for i in range(len(flat)):
        sv = int(flat[i]) & ((1 << config.bits_per_sample) - 1)
        for b in range(config.bits_per_sample - 1, -1, -1):
            all_bits.append((sv >> b) & 1)
    bits = np.array(all_bits, dtype=np.uint8)
    if len(bits) < 32:
        return ""
    dl = 0
    for b in bits[:32]:
        dl = (dl << 1) | int(b)
    return bits_to_text(bits[32:32 + dl])


def encode_phase(audio, text, config):
    data_bits = _add_header(text_to_bits(text))
    chs = [audio.copy()] if audio.ndim == 1 else [audio[ch].copy() for ch in range(audio.shape[0])]
    result = []
    for ch in chs:
        fs = 2048
        hop = fs // 2
        f, t, Zxx = scipy_signal.stft(ch, fs=config.sample_rate, nperseg=fs, noverlap=fs - hop)
        mod = Zxx.copy()
        cb = min(int(config.carrier_freq * fs / config.sample_rate), mod.shape[0] - 1)
        for bi in range(min(len(data_bits), mod.shape[1])):
            mod[cb, bi] *= np.exp(1j * int(data_bits[bi]) * (np.pi / 4))
        _, rec = scipy_signal.istft(mod, fs=config.sample_rate, nperseg=fs, noverlap=fs - hop)
        rec = rec[:len(ch)]
        if len(rec) < len(ch):
            rec = np.pad(rec, (0, len(ch) - len(rec)))
        result.append(rec)
    return result[0] if audio.ndim == 1 else np.array(result)


def decode_phase(audio, config):
    ch = audio[0] if audio.ndim > 1 else audio
    fs = 2048
    hop = fs // 2
    f, t, Zxx = scipy_signal.stft(ch, fs=config.sample_rate, nperseg=fs, noverlap=fs - hop)
    cb = min(int(config.carrier_freq * fs / config.sample_rate), Zxx.shape[0] - 1)
    bits = np.array([1 if abs(np.angle(Zxx[cb, i])) > np.pi / 8 else 0 for i in range(Zxx.shape[1])], dtype=np.uint8)
    if len(bits) < 32:
        return ""
    dl = 0
    for b in bits[:32]:
        dl = (dl << 1) | int(b)
    return bits_to_text(bits[32:32 + dl])


def _pn(length, seed=42):
    return np.random.RandomState(seed).choice([-1, 1], size=length).astype(np.float32)


def encode_spread_spectrum(audio, text, config):
    data_bits = _add_header(text_to_bits(text))
    flat = audio.flatten().copy()
    cpb = config.spread_factor
    if len(data_bits) * cpb > len(flat):
        raise ValueError("Audio too short")
    pn0, pn1 = _pn(cpb, 42), _pn(cpb, 123)
    for i, bit in enumerate(data_bits):
        s, e = i * cpb, (i + 1) * cpb
        if e > len(flat):
            break
        flat[s:e] += 0.01 * (pn1 if bit else pn0)
    return flat.reshape(audio.shape) if audio.ndim > 1 else flat


def decode_spread_spectrum(audio, config):
    flat = audio.flatten()
    cpb = config.spread_factor
    pn0, pn1 = _pn(cpb, 42), _pn(cpb, 123)
    bits = []
    i = 0
    while (i + 1) * cpb <= len(flat):
        seg = flat[i * cpb:(i + 1) * cpb]
        bits.append(1 if np.dot(seg, pn1) > np.dot(seg, pn0) else 0)
        i += 1
    arr = np.array(bits, dtype=np.uint8)
    if len(arr) < 32:
        return ""
    dl = 0
    for b in arr[:32]:
        dl = (dl << 1) | int(b)
    return bits_to_text(arr[32:32 + dl])


def encode(audio, text, config):
    m = {StegoMethod.LSB: encode_lsb, StegoMethod.PHASE_ENCODING: encode_phase, StegoMethod.SPREAD_SPECTRUM: encode_spread_spectrum}
    return m[config.method](audio, text, config)


def decode(audio, config):
    m = {StegoMethod.LSB: decode_lsb, StegoMethod.PHASE_ENCODING: decode_phase, StegoMethod.SPREAD_SPECTRUM: decode_spread_spectrum}
    return m[config.method](audio, config)