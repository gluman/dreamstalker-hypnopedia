import numpy as np
from scipy import signal
from scipy.io import wavfile
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import json

from core.binaural import generate_night_progression
from core.steganography import encode as stego_encode, StegoConfig as StegoStegoConfig, StegoMethod


@dataclass
class AmbientConfig:
    sample_rate: int = 44100
    pink_noise_amplitude: float = 0.15
    nature_volume: float = 0.08
    wind_freq_range: Tuple[float, float] = (80.0, 400.0)
    wind_mod_rate: float = 0.15
    bird_freq_range: Tuple[float, float] = (2000.0, 5000.0)
    bird_chance: float = 0.002
    cricket_freq: float = 4500.0
    cricket_rate: float = 12.0


class AmbientGenerator:
    def __init__(self, config: Optional[AmbientConfig] = None):
        self.cfg = config or AmbientConfig()

    def generate_pink_noise(self, duration_sec: float) -> np.ndarray:
        n_samples = int(self.cfg.sample_rate * duration_sec)
        white = np.random.randn(n_samples)
        b_coeffs = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
        a_coeffs = [1.0, -2.494956002, 2.017265875, -0.522189400]
        pink = signal.lfilter(b_coeffs, a_coeffs, white)
        pink = pink / np.max(np.abs(pink))
        return pink * self.cfg.pink_noise_amplitude

    def generate_wind(self, duration_sec: float) -> np.ndarray:
        n_samples = int(self.cfg.sample_rate * duration_sec)
        t = np.arange(n_samples) / self.cfg.sample_rate
        freq_lo, freq_hi = self.cfg.wind_freq_range
        base_noise = np.random.randn(n_samples)
        sos = signal.butter(4, [freq_lo, freq_hi], btype='band',
                            fs=self.cfg.sample_rate, output='sos')
        filtered = signal.sosfilt(sos, base_noise)
        modulator = 0.5 + 0.5 * np.sin(2 * np.pi * self.cfg.wind_mod_rate * t)
        return filtered * modulator * self.cfg.nature_volume

    def generate_cricket_chirps(self, duration_sec: float) -> np.ndarray:
        n_samples = int(self.cfg.sample_rate * duration_sec)
        output = np.zeros(n_samples)
        samples_per_chirp = int(0.02 * self.cfg.sample_rate)
        chirp_env = np.hanning(samples_per_chirp)
        interval = int(self.cfg.sample_rate / self.cfg.cricket_rate)
        t_chirp = np.arange(samples_per_chirp) / self.cfg.sample_rate
        chirp_signal = np.sin(2 * np.pi * self.cfg.cricket_freq * t_chirp) * chirp_env
        for pos in range(0, n_samples - samples_per_chirp, interval):
            jitter = np.random.randint(-interval // 4, interval // 4)
            start = max(0, pos + jitter)
            end = min(n_samples, start + samples_per_chirp)
            actual_len = end - start
            output[start:end] += chirp_signal[:actual_len] * 0.5
        return output * self.cfg.nature_volume

    def generate_bird_calls(self, duration_sec: float) -> np.ndarray:
        n_samples = int(self.cfg.sample_rate * duration_sec)
        output = np.zeros(n_samples)
        samples_per_call = int(0.15 * self.cfg.sample_rate)
        t_call = np.arange(samples_per_call) / self.cfg.sample_rate
        n_calls = int(self.cfg.cricket_rate * duration_sec * self.cfg.bird_chance * 100)
        for _ in range(n_calls):
            start = np.random.randint(0, max(1, n_samples - samples_per_call))
            freq = np.random.uniform(*self.cfg.bird_freq_range)
            freq_slide = np.random.uniform(-200, 200)
            inst_freq = freq + freq_slide * t_call / t_call[-1]
            call = np.sin(2 * np.pi * np.cumsum(inst_freq) / self.cfg.sample_rate)
            env = np.hanning(samples_per_call)
            output[start:start + samples_per_call] += call * env * 0.3
        return output * self.cfg.nature_volume

    def generate(self, duration_sec: float) -> np.ndarray:
        pink = self.generate_pink_noise(duration_sec)
        wind = self.generate_wind(duration_sec)
        crickets = self.generate_cricket_chirps(duration_sec)
        birds = self.generate_bird_calls(duration_sec)
        mixed = pink + wind + crickets + birds
        return np.clip(mixed, -1.0, 1.0)


@dataclass
class TMRConfig:
    sample_rate: int = 44100
    cue_duration: float = 0.5
    cue_freq: float = 1000.0
    cue_volume: float = 0.12
    fade_ms: float = 50.0
    min_interval: float = 180.0
    max_interval: float = 600.0


class TMRGenerator:
    def __init__(self, config: Optional[TMRConfig] = None):
        self.cfg = config or TMRConfig()

    def generate_cue(self, freq: Optional[float] = None) -> np.ndarray:
        freq = freq or self.cfg.cue_freq
        n_samples = int(self.cfg.sample_rate * self.cfg.cue_duration)
        t = np.arange(n_samples) / self.cfg.sample_rate
        tone = np.sin(2 * np.pi * freq * t)
        tone *= np.sin(2 * np.pi * (freq * 1.5) * t) * 0.3
        fade_samples = int(self.cfg.sample_rate * self.cfg.fade_ms / 1000)
        env = np.ones(n_samples)
        env[:fade_samples] = np.linspace(0, 1, fade_samples)
        env[-fade_samples:] = np.linspace(1, 0, fade_samples)
        return tone * env * self.cfg.cue_volume

    def generate_cue_sequence(self, knowledge_count: int,
                              duration_sec: float) -> List[Tuple[float, np.ndarray]]:
        cues = []
        position = self.cfg.min_interval
        interval = max(self.cfg.min_interval,
                       min(self.cfg.max_interval, duration_sec / (knowledge_count + 1)))
        for i in range(knowledge_count):
            if position >= duration_sec:
                break
            freq = self.cfg.cue_freq + (i % 8) * 100
            cue = self.generate_cue(freq)
            cues.append((position, cue))
            position += interval + np.random.uniform(-10, 10)
        return cues


@dataclass
class NightConfig:
    sample_rate: int = 44100
    ambient: AmbientConfig = field(default_factory=AmbientConfig)
    tmr: TMRConfig = field(default_factory=TMRConfig)
    sleep_phases: dict = field(default_factory=lambda: {
        'alpha': (0, 20),
        'theta': (20, 60),
        'delta': (60, 480),
    })


class NightAudioGenerator:
    def __init__(self, config: Optional[NightConfig] = None):
        self.cfg = config or NightConfig()
        self.ambient_gen = AmbientGenerator(self.cfg.ambient)
        self.tmr_gen = TMRGenerator(self.cfg.tmr)

    def _mix_layer(self, base: np.ndarray, layer: np.ndarray,
                   start_sample: int, volume: float = 1.0):
        end = start_sample + len(layer)
        if end > len(base):
            layer = layer[:len(base) - start_sample]
            end = len(base)
        if len(layer) <= 0:
            return
        base[start_sample:end] += layer * volume

    def _fade_transition(self, duration_sec: float, fade_in_sec: float = 3.0) -> np.ndarray:
        n = int(self.cfg.sample_rate * duration_sec)
        fade_n = int(self.cfg.sample_rate * fade_in_sec)
        env = np.ones(n)
        if fade_n > 0:
            env[:fade_n] = np.linspace(0, 1, min(fade_n, n))
        return env

    def generate_full_night(self, hours: float, knowledge_items: List[str],
                            output_path: str) -> str:
        duration_sec = hours * 3600
        n_samples = int(self.cfg.sample_rate * duration_sec)
        track = np.zeros(n_samples, dtype=np.float64)

        ambient = self.ambient_gen.generate(duration_sec)
        track += ambient

        binaural_audio = generate_night_progression(
            total_hours=hours, sample_rate=self.cfg.sample_rate
        )
        # Mix stereo binaural to mono for track
        if binaural_audio.ndim == 2:
            binaural_mono = binaural_audio.mean(axis=0)
        else:
            binaural_mono = binaural_audio

        if len(binaural_mono) < n_samples:
            binaural_mono = np.pad(binaural_mono, (0, n_samples - len(binaural_mono)))
        track += binaural_mono[:n_samples] * 0.25

        # Encode knowledge text via steganography
        if knowledge_items:
            stego_cfg = StegoStegoConfig(method=StegoMethod.LSB, sample_rate=self.cfg.sample_rate)
            text_data = " ||| ".join(str(item) for item in knowledge_items)
            # Use a copy of binaural as carrier for stego encoding
            carrier = binaural_mono[:n_samples].copy()
            stego_audio = stego_encode(carrier, text_data, stego_cfg)
            if stego_audio.ndim == 2:
                stego_audio = stego_audio.mean(axis=0)
            if len(stego_audio) >= n_samples:
                track += stego_audio[:n_samples] * 0.05

        tmr_cues = self.tmr_gen.generate_cue_sequence(len(knowledge_items), duration_sec)
        for position_sec, cue in tmr_cues:
            start_sample = int(position_sec * self.cfg.sample_rate)
            self._mix_layer(track, cue, start_sample)

        track = np.clip(track, -1.0, 1.0)
        track_int = (track * 32767).astype(np.int16)
        wavfile.write(output_path, self.cfg.sample_rate, track_int)
        return output_path


    def generate_falling_asleep_phase(self, items, installation_text,
                                      compress_rate=20.0, duration_min=25.0,
                                      output_path=None):
        sr = self.cfg.sample_rate
        duration_sec = duration_min * 60
        n_samples = int(sr * duration_sec)
        track = np.zeros(n_samples, dtype=np.float64)

        # Phase 1: Installation (0-60s)
        install_sec = 60.0
        install_n = int(sr * install_sec)
        install_track = np.zeros(install_n, dtype=np.float64)
        pink = self.ambient_gen.generate_pink_noise(install_sec)
        install_track += pink * 0.4
        t = np.arange(install_n) / sr
        alpha_tone = np.sin(2 * np.pi * 200 * t)
        alpha_tone = alpha_tone * (0.5 + 0.5 * np.sin(2 * np.pi * 10 * t)) * 0.15
        install_track += alpha_tone
        stego_cfg = StegoStegoConfig(method=StegoMethod.LSB, sample_rate=sr)
        carrier = np.random.randn(install_n).astype(np.float32) * 0.005
        stego = stego_encode(carrier, installation_text, stego_cfg)
        if stego.ndim > 1:
            stego = stego.mean(axis=0)
        install_track += stego[:install_n] * 0.1
        fade_n = int(sr * 5)
        install_track[:fade_n] *= np.linspace(0, 1, fade_n)
        track[:install_n] += install_track

        # Phase 2: Decoder (60s-180s)
        from core.anchor_generator import AnchorGenerator
        anchor_gen = AnchorGenerator(sample_rate=sr)
        decoder_start = install_n
        current_pos = decoder_start
        for ii, item in enumerate(items[:10]):
            if current_pos >= decoder_start + int(120 * sr):
                break
            for rep in range(2):
                anchor = anchor_gen.generate_anchor(ii)
                self._mix_layer(track, anchor, current_pos, volume=0.3)
                current_pos += len(anchor) + int(0.3 * sr)
                ft = item.get('fact', '')
                fd = max(1.0, len(ft.split()) * 0.3)
                fn = int(sr * fd)
                if current_pos + fn > len(track):
                    break
                tf = np.arange(fn) / sr
                fton = np.sin(2 * np.pi * 440 * tf) * 0.1
                fton = fton * (np.sin(2 * np.pi * 3 * tf) * 0.5 + 0.5)
                sf = stego_encode(fton.copy(), ft, stego_cfg)
                if sf.ndim > 1:
                    sf = sf.mean(axis=0)
                self._mix_layer(track, sf[:fn], current_pos, volume=0.15)
                current_pos += fn + int(0.5 * sr)

        if duration_sec <= 180:
            track = np.clip(track, -1.0, 1.0)
            if output_path:
                track_int = (track * 32767).astype(np.int16)
                wavfile.write(output_path, sr, track_int)
                return output_path
            return track
        
        # Phase 3: Main package (180s-end)
        main_start = int(180 * sr)
        main_sec = duration_sec - 180
        main_n = int(main_sec * sr)
        main_track = np.zeros(main_n, dtype=np.float64)
        ambient = self.ambient_gen.generate(main_sec)
        main_track += ambient
        from core.binaural import generate_sweep
        binaural = generate_sweep(10.0, 5.0, main_sec, sr, 200.0, 0.3)
        if binaural.ndim == 2:
            binaural = binaural.mean(axis=0)
        main_track += binaural[:main_n] * 0.2
        anchor_interval = int(25 * sr)
        pos = 0
        aidx = 0
        while pos < main_n:
            anchor = anchor_gen.generate_anchor(aidx % max(1, len(items)))
            if pos + len(anchor) <= main_n:
                main_track[pos:pos + len(anchor)] += anchor * 0.2
            pos += anchor_interval
            aidx += 1
        all_facts = sep.join(item.get('fact', '') for item in items)
        stego_main = stego_encode(ambient.copy(), all_facts, stego_cfg)
        if stego_main.ndim > 1:
            stego_main = stego_main.mean(axis=0)
        main_track += stego_main[:main_n] * 0.03
        actual_main = min(main_n, n_samples - main_start)
        track[main_start:main_start + actual_main] += main_track[:actual_main]

        track = np.clip(track, -1.0, 1.0)
        if output_path:
            track_int = (track * 32767).astype(np.int16)
            wavfile.write(output_path, sr, track_int)
            return output_path
        return track

    def generate_presleep_suggestion(self, text: str, output_path: str) -> str:
        duration_sec = 30.0
        n_samples = int(self.cfg.sample_rate * duration_sec)
        track = np.zeros(n_samples, dtype=np.float64)

        ambient = self.ambient_gen.generate_pink_noise(duration_sec)
        track += ambient * 0.5

        t = np.arange(n_samples) / self.cfg.sample_rate
        alpha = 0.5 + 0.5 * np.sin(2 * np.pi * 10 * t)
        carrier = np.sin(2 * np.pi * 200 * t) * alpha * 0.15
        track += carrier

        stego_cfg = StegoStegoConfig(method=StegoMethod.LSB, sample_rate=self.cfg.sample_rate)
        carrier = np.random.randn(n_samples).astype(np.float32) * 0.01
        stego_audio = stego_encode(carrier, text, stego_cfg)
        if isinstance(stego_audio, np.ndarray):
            if len(stego_audio) < n_samples:
                stego_audio = np.pad(stego_audio, (0, n_samples - len(stego_audio)))
            track += stego_audio[:n_samples] * 0.1

        fade = self._fade_transition(duration_sec, fade_in_sec=5.0)
        track *= fade

        track = np.clip(track, -1.0, 1.0)
        track_int = (track * 32767).astype(np.int16)
        wavfile.write(output_path, self.cfg.sample_rate, track_int)
        return output_path
