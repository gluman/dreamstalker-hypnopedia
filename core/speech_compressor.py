import numpy as np
import os
import re

try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    from scipy import signal
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


def estimate_duration(text: str) -> float:
    if not text:
        return 0.0
    words = len(re.findall(r'\S+', text))
    cyrillic = len(re.findall(r'[\u0400-\u04FF]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))
    if cyrillic > latin:
        return words / 3.0
    return words / 4.0


class SpeechCompressor:
    def __init__(self, tts_engine='pyttsx3', sample_rate=44100):
        self.tts_engine = tts_engine
        self.sample_rate = sample_rate
        self._engine = None
        if HAS_PYTTSX3 and tts_engine == 'pyttsx3':
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty('rate', 150)
            except Exception:
                self._engine = None

    def text_to_speech(self, text: str, output_path: str = None) -> np.ndarray:
        duration = estimate_duration(text)
        if self._engine and HAS_PYTTSX3:
            try:
                if output_path:
                    self._engine.save_to_file(text, output_path)
                    self._engine.runAndWait()
                    audio, sr = librosa.load(output_path, sr=self.sample_rate) if HAS_LIBROSA else (None, 0)
                    if audio is not None:
                        return audio
                else:
                    import tempfile
                    tmp = tempfile.mktemp(suffix='.wav')
                    self._engine.save_to_file(text, tmp)
                    self._engine.runAndWait()
                    if os.path.exists(tmp):
                        if HAS_LIBROSA:
                            audio, sr = librosa.load(tmp, sr=self.sample_rate)
                        else:
                            import wave
                            with wave.open(tmp, 'r') as wf:
                                frames = wf.readframes(wf.getnframes())
                                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
                            os.unlink(tmp)
                            return audio
                        os.unlink(tmp)
                        return audio
            except Exception:
                pass
        return self._synthetic_placeholder(duration)

    def _synthetic_placeholder(self, duration: float) -> np.ndarray:
        if duration <= 0:
            duration = 0.1
        t = np.linspace(0, duration, int(self.sample_rate * duration), endpoint=False)
        freq = 200 + 100 * np.sin(2 * np.pi * 3 * t)
        audio = 0.3 * np.sin(2 * np.pi * np.cumsum(freq) / self.sample_rate)
        envelope = np.minimum(t / 0.05, 1.0) * np.minimum((duration - t) / 0.05, 1.0)
        return (audio * envelope).astype(np.float32)

    def compress(self, audio: np.ndarray, rate: float = 20.0) -> np.ndarray:
        if rate <= 0 or rate == 1.0 or len(audio) < 2:
            return audio
        min_length = max(int(self.sample_rate * 0.05), 16)
        if len(audio) < min_length:
            audio = np.pad(audio, (0, min_length - len(audio)), mode='constant')
        if HAS_LIBROSA:
            try:
                stretched = librosa.effects.time_stretch(audio, rate=rate)
                return stretched.astype(np.float32)
            except Exception:
                pass
        new_length = max(1, int(len(audio) / rate))
        indices = np.linspace(0, len(audio) - 1, new_length)
        compressed = np.interp(indices, np.arange(len(audio)), audio)
        return compressed.astype(np.float32)

    def prepare_knowledge_item(self, item: dict) -> np.ndarray:
        parts = []
        for key in ('fact', 'association', 'flashcard_q', 'flashcard_a'):
            text = item.get(key, '')
            if text:
                audio = self.text_to_speech(text)
                parts.append(audio)
        if not parts:
            return np.zeros(int(self.sample_rate * 0.5), dtype=np.float32)
        silence = np.zeros(int(self.sample_rate * 0.3), dtype=np.float32)
        result = parts[0]
        for p in parts[1:]:
            result = np.concatenate([result, silence, p])
        return result

    def prepare_package(self, items: list, compress_rate: float = 20.0) -> np.ndarray:
        compressed_parts = []
        silence = np.zeros(int(self.sample_rate * 0.5), dtype=np.float32)
        for item in items:
            audio = self.prepare_knowledge_item(item)
            compressed = self.compress(audio, rate=compress_rate)
            compressed_parts.append(compressed)
            compressed_parts.append(silence)
        if not compressed_parts:
            return np.zeros(int(self.sample_rate), dtype=np.float32)
        return np.concatenate(compressed_parts)
