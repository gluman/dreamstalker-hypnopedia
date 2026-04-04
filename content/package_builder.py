import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class PackageBuilder:
    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self._color_pool = [
            "красный", "синий", "зелёный", "жёлтый", "фиолетовый",
            "оранжевый", "белый", "чёрный", "золотой", "серебряный"
        ]
        self._shape_pool = [
            "круг", "квадрат", "треугольник", "звезда", "спираль",
            "линия", "точка", "ромб", "овал", "волна"
        ]
        self._noun_exclusions = {
            "это", "в", "на", "с", "и", "или", "из", "к", "по", "за",
            "от", "до", "для", "при", "об", "без", "через", "про",
            "the", "a", "an", "in", "on", "of", "to", "for", "is", "are"
        }

    def build_sleep_package(self, items: list[dict], compress_rate: float = 20.0) -> dict:
        enriched = []
        for i, item in enumerate(items):
            fact = item["fact"]
            enriched.append({
                "fact": fact,
                "association": self._auto_association(fact),
                "flashcard_q": self._create_flashcard(fact)[0],
                "flashcard_a": self._create_flashcard(fact)[1],
                "anchor_freq": self._assign_anchor_freq(i),
                "anchor_index": i,
            })
        metadata = {
            "item_count": len(enriched),
            "compress_rate": compress_rate,
            "created_at": datetime.now().isoformat(),
        }
        return {"items": enriched, "metadata": metadata}

    def build_decoder_package(self, items: list[dict]) -> dict:
        decoder_items = []
        for i, item in enumerate(items):
            decoder_items.append({
                "anchor_freq": self._assign_anchor_freq(i),
                "normal_speed_fact": item["fact"],
                "repetitions": 3,
            })
        return {"items": decoder_items, "metadata": {"type": "decoder", "item_count": len(decoder_items)}}

    def build_installation_text(self, goal: str, item_count: int) -> str:
        return (
            f"Сейчас вам будет передана информация о {goal}. "
            f"Количество элементов: {item_count}. "
            "Каждый звуковой сигнал — ключ к воспоминанию. "
            "Мозг обработает и запомнит. "
            "После прослушивания вы уснёте, и мозг завершит обработку."
        )

    def format_for_steganography(self, items: list[dict]) -> str:
        parts = []
        for item in items:
            category = item.get("category", "")
            fact = item["fact"]
            parts.append(f"[{category}] {fact}")
        return "|||".join(parts)

    def save_package(self, package: dict, output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_package(self, input_path: str) -> dict:
        path = Path(input_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def _auto_association(self, fact: str) -> str:
        words = fact.lower().split()
        noun = None
        for w in words:
            cleaned = w.strip(".,;:!?()[]{}\"'")
            if len(cleaned) > 3 and cleaned not in self._noun_exclusions:
                noun = cleaned
                break
        if noun is None:
            noun = words[0] if words else "объект"
        hash_val = sum(ord(c) for c in noun)
        color = self._color_pool[hash_val % len(self._color_pool)]
        shape = self._shape_pool[(hash_val // len(self._color_pool)) % len(self._shape_pool)]
        return f"{color} {shape} — {noun}"

    def _create_flashcard(self, fact: str) -> tuple:
        words = fact.split()
        key_word = None
        key_idx = None
        for i, w in enumerate(words):
            cleaned = w.strip(".,;:!?()[]{}\"'")
            if len(cleaned) > 3 and cleaned.lower() not in self._noun_exclusions:
                key_word = cleaned
                key_idx = i
                break
        if key_word is None and words:
            key_idx = len(words) // 2
            key_word = words[key_idx].strip(".,;:!?()[]{}\"'")
        if key_word:
            question_words = list(words)
            question_words[key_idx] = question_words[key_idx].replace(key_word, "____", 1)
            question = " ".join(question_words)
            answer = key_word
        else:
            question = "____"
            answer = fact
        return (question, answer)

    def _assign_anchor_freq(self, index: int) -> float:
        return 800.0 + index * 100.0
