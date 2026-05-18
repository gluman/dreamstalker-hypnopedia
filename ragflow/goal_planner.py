import re
import requests
from ragflow_sdk import RAGFlow


class GoalPlanner:
    def __init__(self, base_url: str, api_key: str, dataset_id: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.dataset_id = dataset_id
        self.rag = RAGFlow(api_key=api_key, base_url=base_url)

    def collect_materials(self, goal_description: str, max_chunks: int = 30) -> list[dict]:
        try:
            resp = self.rag.retrieve(
                question=goal_description,
                dataset_ids=[self.dataset_id],
                page=1,
                page_size=max_chunks,
            )
        except Exception as e:
            raise ConnectionError(f"RAGFlow unavailable: {e}") from e
        chunks = []
        for item in resp:
            chunks.append({
                "content": item.content if hasattr(item, "content") else str(item),
                "source": getattr(item, "document_name", "") or getattr(item, "document_id", "unknown"),
                "similarity": float(getattr(item, "similarity", 0.0) or 0.0),
            })
        return chunks

    def extract_key_facts(self, chunks: list[dict], count: int = 20) -> list[dict]:
        if not chunks:
            return []
        keywords = self._keywords_from_chunks(chunks)
        candidates = []
        seen_sources = set()
        for chunk in chunks:
            sentences = self._extract_sentences(chunk["content"], keywords)
            for sent in sentences:
                candidates.append({
                    "fact": sent,
                    "source": chunk["source"],
                    "category": self._guess_category(sent),
                    "similarity": chunk["similarity"],
                })
        candidates = self._deduplicate(candidates)
        candidates = self._score_items(candidates, chunks)
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        return [{"fact": c["fact"], "source": c["source"], "category": c["category"]} for c in candidates[:count]]

    def create_learning_plan(self, goal_description: str, items_count: int = 20) -> dict:
        chunks = self.collect_materials(goal_description)
        items = self.extract_key_facts(chunks, count=items_count)
        sources = list({c["source"] for c in chunks})
        return {
            "goal": goal_description,
            "items": items,
            "sources": sources,
            "items_count": len(items),
        }

    def create_test_items(self, items: list[dict], test_count: int = 10) -> list[dict]:
        tests = []
        for idx, item in enumerate(items[:test_count]):
            fact = item["fact"]
            words = fact.split()
            if len(words) > 6:
                mid = len(words) // 2
                blanked = " ".join(words[:mid]) + " ______ " + " ".join(words[mid + 2:])
                tests.append({
                    "question": f"Fill in the blank: {blanked}",
                    "answer": " ".join(words[mid:mid + 2]),
                    "item_id": idx,
                    "type": "recall",
                })
            else:
                tests.append({
                    "question": f"What do you know about: {item.get('category', 'this topic')}?",
                    "answer": fact,
                    "item_id": idx,
                    "type": "definition",
                })
            if idx % 3 == 0 and idx + 1 < len(items):
                tests.append({
                    "question": f"Name a fact related to: {item['category']}",
                    "answer": items[idx + 1]["fact"] if idx + 1 < len(items) else fact,
                    "item_id": idx,
                    "type": "association",
                })
        return tests[:test_count]

    def _keywords_from_chunks(self, chunks: list[dict]) -> list[str]:
        text = " ".join(c["content"] for c in chunks)
        words = re.findall(r"[A-Za-zА-Яа-яёЁ]{4,}", text.lower())
        freq = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        ranked = sorted(freq.items(), key=lambda x: -x[1])
        return [w for w, _ in ranked[:30]]

    def _extract_sentences(self, text: str, keywords: list) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        kw_set = set(k.lower() for k in keywords)
        result = []
        for sent in sentences:
            sent_clean = sent.strip()
            if len(sent_clean) < 15 or len(sent_clean) > 500:
                continue
            sent_words = set(re.findall(r"[A-Za-zА-Яа-яёЁ]+", sent_clean.lower()))
            if sent_words & kw_set:
                result.append(sent_clean)
        return result

    def _deduplicate(self, items: list[dict]) -> list[dict]:
        seen = []
        result = []
        for item in items:
            words = set(re.findall(r"[A-Za-zА-Яа-яёЁ]{3,}", item["fact"].lower()))
            is_dup = False
            for prev in seen:
                if len(words & prev) / max(len(words | prev), 1) > 0.7:
                    is_dup = True
                    break
            if not is_dup:
                seen.append(words)
                result.append(item)
        return result

    def _score_items(self, items: list[dict], chunks: list[dict]) -> list[dict]:
        max_sim = max((c["similarity"] for c in chunks), default=1.0) or 1.0
        source_sim = {}
        for c in chunks:
            source_sim[c["source"]] = max(source_sim.get(c["source"], 0), c["similarity"])
        for item in items:
            sim = source_sim.get(item["source"], 0) / max_sim
            length_bonus = min(len(item["fact"]) / 200, 1.0)
            item["score"] = sim * 0.7 + length_bonus * 0.3
        return items

    @staticmethod
    def _guess_category(text: str) -> str:
        lower = text.lower()
        if any(w in lower for w in ["define", "is a", "means", "refers to"]):
            return "definition"
        if any(w in lower for w in ["because", "therefore", "result", "cause"]):
            return "causation"
        if any(w in lower for w in ["example", "such as", "including", "for instance"]):
            return "example"
        if re.search(r"\d", text):
            return "data"
        return "fact"
