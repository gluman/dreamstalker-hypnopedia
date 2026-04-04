import re
from typing import List, Dict, Any
from .client import RAGFlowClient


class Summarizer:
    def __init__(self, client: RAGFlowClient):
        self.client = client

    def summarize_for_sleep(self, content: str, max_length: int = 500) -> str:
        prompt = f"""Summarize for unconscious mind sleep learning.
Content: {content[:2000]}
Rules:
- Use simple nouns and verbs
- Short declarative sentences
- Repeat key points 3x
- Rhythmic patterns preferred
Max {max_length} chars."""

        answer = self.client.chat("", prompt)
        if answer and len(answer) > max_length:
            answer = answer[:max_length] + "..."
        return answer

    def extract_key_facts(self, content: str) -> List[str]:
        prompt = f"""Extract 10 key facts from:
{content[:2000]}
Return ONLY JSON array of strings.
Each fact: single clear statement."""

        answer = self.client.chat("", prompt)
        facts = []
        try:
            import json
            facts = json.loads(answer) if answer else []
        except:
            lines = answer.split("\n") if answer else []
            facts = [re.sub(r'^\d+\.\s*', "", l).strip() for l in lines if l.strip()]

        return facts[:10] if len(facts) > 10 else facts if facts else [content[:100]]

    def create_night_script(self, knowledge_items: List[str]) -> str:
        if not knowledge_items:
            return ""

        facts = self.extract_key_facts(" ".join(knowledge_items[:3]))
        summary = self.summarize_for_sleep(" ".join(facts), max_length=300)

        parts = [
            "=== SLEEP ENCODING SCRIPT ===",
            f"[REPEAT 3x] {summary}",
            "",
            "KEY FACTS:"
        ]
        for i, fact in enumerate(facts, 1):
            parts.append(f"{i}. {fact} [REPEAT 3x]")

        parts.extend([
            "",
            "=== END SCRIPT ===",
            "Think silently during playback"
        ])

        return "\n".join(parts)

    def compress_for_encoding(self, content: str) -> str:
        return re.sub(r'\s+', ' ', content).strip()

    def create_binaural_script(self, facts: List[str]) -> str:
        lines = []
        for i, fact in enumerate(facts):
            fact_compressed = self.compress_for_encoding(fact)
            lines.append(f"[LEFT EAR] {fact_compressed}")
            lines.append(f"[RIGHT EAR] {fact_compressed[::-1]}")
            lines.append("[PAUSE 5s]")
        return "\n".join(lines)