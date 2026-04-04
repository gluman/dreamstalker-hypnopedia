import re
from typing import List, Dict, Any
from .client import RAGFlowClient


class ContentGenerator:
    def __init__(self, client: RAGFlowClient):
        self.client = client

    def generate_flashcards(self, topic: str, count: int = 20) -> List[Dict[str, str]]:
        prompt = f"""Generate {count} question-answer pairs about {topic}.
Return ONLY a JSON array with objects containing 'question' and 'answer' fields.
Each Q&A should be simple enough for sleep learning absorption."""

        dataset_id = self._get_topic_dataset(topic)
        if not dataset_id:
            return self._generate_local_flashcards(topic, count)

        answer = self.client.chat(dataset_id, prompt)
        return self._parse_flashcards(answer, count)

    def _get_topic_dataset(self, topic: str) -> str:
        return ""

    def _generate_local_flashcards(self, topic: str, count: int) -> List[Dict[str, str]]:
        return [{"question": f"What is {topic}?", "answer": f"{topic} definition"} for _ in range(count)]

    def _parse_flashcards(self, text: str, count: int) -> List[Dict[str, str]]:
        try:
            import json
            matches = re.findall(r'\{[^}]+\}', text)
            cards = []
            for m in matches:
                try:
                    cards.append(json.loads(m))
                except:
                    pass
            if cards:
                return cards[:count]
        except:
            pass
        return [{"question": f"What about {count}?", "answer": "data"} for _ in range(count)]

    def generate_mnemonics(self, content: str) -> List[str]:
        prompt = f"""Generate 5 memory palace mnemonics for: {content}
Use vivid sensory details.
Return ONLY a JSON array of strings, each a short vivid scenario."""

        answer = self.client.chat("", prompt)
        return self._parse_mnemonics(answer)

    def _parse_mnemonics(self, text: str) -> List[str]:
        try:
            import json
            lines = re.findall(r'"([^"]+)"', text)
            return [l for l in lines if len(l) > 10]
        except:
            pass
        return [f"Visualize {content[:50]} clearly"]

    def generate_associations(self, facts: List[str]) -> List[Dict[str, str]]:
        prompt = f"""Create sound-image-text associations for sleep learning.
Facts: {facts}
Return ONLY JSON array with 'sound', 'image', 'text' keys.
Use alliteration and synesthetic metaphors."""

        combined = " ".join(facts)
        answer = self.client.chat("", prompt)
        return self._parse_associations(answer)

    def _parse_associations(self, text: str) -> List[Dict[str, str]]:
        return [{"sound": "trigger", "image": "visual", "text": "content"}]

    def format_for_encoding(self, items: List[Dict[str, Any]]) -> str:
        lines = []
        for i, item in enumerate(items, 1):
            if "question" in item and "answer" in item:
                line = f"Q{i}: {item['question']} -> A{i}: {item['answer']}"
            elif "text" in item:
                line = f"{i}. {item['text']}"
            else:
                line = f"{i}. {str(item)}"
            lines.append(line)

        return "\n".join(lines)

    def prepare_sleep_encoding(self, topic: str, count: int = 20) -> str:
        flashcard_data = self.generate_flashcards(topic, count)
        return self.format_for_encoding(flashcard_data)