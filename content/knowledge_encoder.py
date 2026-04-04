# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import List

@dataclass
class KnowledgeItem:
    content: str
    category: str = "general"
    repetitions: int = 3
    priority: int = 1

@dataclass
class Flashcard:
    question: str
    answer: str
    hint: str = ""

@dataclass
class VocabularyItem:
    word: str
    translation: str
    context: str = ""

class KnowledgeEncoder:
    def encode_flashcard(self, fc: Flashcard) -> str:
        return f"Q: {fc.question}|||A: {fc.answer}"

    def encode_vocabulary(self, item: VocabularyItem) -> str:
        return f"WORD: {item.word}|||TRANSLATION: {item.translation}|||CONTEXT: {item.context}"

    def encode_fact(self, fact: str, association: str = "") -> str:
        return f"FACT: {fact}|||ASSOCIATION: {association}" if association else f"FACT: {fact}"

    def create_night_batch(self, items: List[KnowledgeItem], duration_hours: float = 8.0) -> List[dict]:
        total_reps = sum(item.repetitions for item in items)
        interval = (duration_hours * 3600) / max(total_reps, 1)
        batch, t = [], 0.0
        for item in items:
            for rep in range(item.repetitions):
                batch.append({"time_sec": t, "content": item.content, "category": item.category, "repetition": rep + 1})
                t += interval
        return batch

    def encode_for_steganography(self, items: List[KnowledgeItem]) -> str:
        return "|||".join(f"[{it.category}] {it.content}" for it in items)
