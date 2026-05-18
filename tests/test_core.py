"""Unit tests for core audio modules."""

import numpy as np
import pytest

from core.binaural import (
    generate_binaural_beats,
    generate_sweep,
    generate_night_progression,
    BinauralConfig,
    WaveType,
    SleepPhase,
    PRESETS,
)
from core.steganography import (
    encode,
    decode,
    StegoConfig,
    StegoMethod,
    text_to_bits,
    bits_to_text,
)
from core.anchor_generator import AnchorGenerator, get_anchor_freq
from content.package_builder import PackageBuilder
from content.test_generator import TestGenerator
from content.knowledge_encoder import KnowledgeEncoder, KnowledgeItem, Flashcard


class TestBinauralBeats:
    def test_generate_binaural_beats_shape(self):
        config = BinauralConfig(duration=1.0, sample_rate=44100)
        audio = generate_binaural_beats(config)
        assert audio.shape == (2, 44100)

    def test_generate_binaural_beats_volume(self):
        config = BinauralConfig(duration=1.0, volume=0.5)
        audio = generate_binaural_beats(config)
        assert np.max(np.abs(audio)) <= 0.5 + 1e-6

    def test_monaural_beats(self):
        config = BinauralConfig(duration=1.0, wave_type=WaveType.MONAURAL)
        audio = generate_binaural_beats(config)
        np.testing.assert_array_almost_equal(audio[0], audio[1])

    def test_isochronic_beats(self):
        config = BinauralConfig(duration=1.0, wave_type=WaveType.ISOCHRONIC)
        audio = generate_binaural_beats(config)
        assert audio.shape == (2, 44100)

    def test_generate_sweep(self):
        audio = generate_sweep(start_freq=10.0, end_freq=4.0, duration=1.0)
        assert audio.shape == (2, 44100)

    def test_night_progression_short(self):
        audio = generate_night_progression(total_hours=0.1, sample_rate=44100)
        assert audio.ndim == 2
        assert audio.shape[1] > 0

    def test_presets_exist(self):
        for phase in SleepPhase:
            assert phase in PRESETS


class TestSteganography:
    def test_text_bits_roundtrip(self):
        original = "Hello, DreamStalker!"
        bits = text_to_bits(original)
        restored = bits_to_text(bits)
        assert original == restored

    def test_encode_decode_lsb(self):
        carrier = np.random.randn(44100).astype(np.float32) * 0.5
        text = "Secret message"
        config = StegoConfig(method=StegoMethod.LSB, sample_rate=44100)
        encoded = encode(carrier, text, config)
        decoded = decode(encoded, config)
        assert decoded == text

    def test_encode_decode_phase(self):
        carrier = np.random.randn(44100).astype(np.float32) * 0.5
        text = "Phase encoded"
        config = StegoConfig(method=StegoMethod.PHASE_ENCODING, sample_rate=44100)
        encoded = encode(carrier, text, config)
        decoded = decode(encoded, config)
        assert decoded == text

    def test_encode_decode_stereo(self):
        carrier = np.random.randn(2, 44100).astype(np.float32) * 0.5
        text = "Stereo test"
        config = StegoConfig(method=StegoMethod.LSB, sample_rate=44100)
        encoded = encode(carrier, text, config)
        decoded = decode(encoded, config)
        assert decoded == text

    def test_audio_too_short_raises_error(self):
        carrier = np.zeros(10, dtype=np.float32)
        text = "This is too long for such a short carrier"
        config = StegoConfig(method=StegoMethod.LSB)
        with pytest.raises(ValueError, match="Audio too short"):
            encode(carrier, text, config)


class TestAnchorGenerator:
    def test_anchor_freq_increases(self):
        assert get_anchor_freq(0) == 800.0
        assert get_anchor_freq(1) == 900.0
        assert get_anchor_freq(5) == 1300.0

    def test_generate_anchor_returns_array(self):
        gen = AnchorGenerator()
        anchor = gen.generate_anchor(0)
        assert isinstance(anchor, np.ndarray)
        assert len(anchor) > 0

    def test_generate_anchor_sequence(self):
        gen = AnchorGenerator()
        seq = gen.generate_anchor_sequence([0, 1, 2])
        assert isinstance(seq, np.ndarray)
        assert len(seq) > gen.generate_anchor(0).shape[0]

    def test_assign_anchors(self):
        gen = AnchorGenerator()
        items = [{"fact": "A"}, {"fact": "B"}]
        result = gen.assign_anchors(items)
        assert result[0]["anchor_index"] == 0
        assert result[0]["anchor_freq"] == 800.0
        assert result[1]["anchor_index"] == 1
        assert result[1]["anchor_freq"] == 900.0


class TestPackageBuilder:
    def test_build_sleep_package(self):
        builder = PackageBuilder()
        items = [{"fact": "The sky is blue", "category": "general"}]
        pkg = builder.build_sleep_package(items)
        assert "items" in pkg
        assert "metadata" in pkg
        assert pkg["metadata"]["item_count"] == 1
        assert "association" in pkg["items"][0]
        assert "flashcard_q" in pkg["items"][0]
        assert "flashcard_a" in pkg["items"][0]

    def test_auto_association(self):
        builder = PackageBuilder()
        assoc = builder._auto_association("Python is a programming language")
        assert isinstance(assoc, str)
        assert len(assoc) > 0

    def test_installation_text(self):
        builder = PackageBuilder()
        text = builder.build_installation_text("Physics", 10)
        assert "Physics" in text
        assert "10" in text

    def test_format_for_steganography(self):
        builder = PackageBuilder()
        items = [{"fact": "Fact 1", "category": "science"}, {"fact": "Fact 2", "category": "math"}]
        result = builder.format_for_steganography(items)
        assert "[science] Fact 1" in result
        assert "[math] Fact 2" in result
        assert "|||" in result


class TestTestGenerator:
    def test_generate_recall_test(self):
        tg = TestGenerator()
        items = [{"fact": "Python is a language", "id": 0}]
        tests = tg.generate_recall_test(items, count=1)
        assert len(tests) == 1
        assert tests[0]["type"] == "recall"

    def test_generate_full_test_suite(self):
        tg = TestGenerator()
        items = [{"fact": f"Fact {i}", "id": i} for i in range(5)]
        suite = tg.generate_full_test_suite(items, tests_per_type=2)
        assert "tests" in suite
        assert "metadata" in suite
        assert suite["metadata"]["total"] > 0

    def test_evaluate_answer_exact(self):
        tg = TestGenerator()
        result = tg.evaluate_answer({"answer": "Python"}, "Python")
        assert result["is_correct"] is True
        assert result["similarity"] == 1.0

    def test_evaluate_answer_case_insensitive(self):
        tg = TestGenerator()
        result = tg.evaluate_answer({"answer": "Python"}, "python")
        assert result["is_correct"] is True

    def test_evaluate_answer_wrong(self):
        tg = TestGenerator()
        result = tg.evaluate_answer({"answer": "Python"}, "JavaScript")
        assert result["is_correct"] is False

    def test_string_similarity(self):
        tg = TestGenerator()
        sim = tg._string_similarity("hello world", "hello there")
        assert 0 < sim < 1


class TestKnowledgeEncoder:
    def test_encode_flashcard(self):
        enc = KnowledgeEncoder()
        fc = Flashcard(question="What is X?", answer="X is Y")
        result = enc.encode_flashcard(fc)
        assert "Q: What is X?" in result
        assert "A: X is Y" in result

    def test_encode_fact(self):
        enc = KnowledgeEncoder()
        result = enc.encode_fact("The sky is blue", "blue sky")
        assert "FACT: The sky is blue" in result
        assert "ASSOCIATION: blue sky" in result

    def test_create_night_batch(self):
        enc = KnowledgeEncoder()
        items = [
            KnowledgeItem(content="Fact 1", repetitions=2),
            KnowledgeItem(content="Fact 2", repetitions=3),
        ]
        batch = enc.create_night_batch(items, duration_hours=1.0)
        assert len(batch) == 5  # 2 + 3 repetitions
