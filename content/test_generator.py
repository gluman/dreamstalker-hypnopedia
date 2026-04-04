import json
from pathlib import Path
from datetime import datetime


class TestGenerator:
    def __init__(self):
        pass

    def generate_recall_test(self, items: list[dict], count: int = 10) -> list[dict]:
        tests = []
        for i, item in enumerate(items[:count]):
            fact = item.get("fact", "")
            keyword = self._extract_keyword(fact)
            tests.append({
                "type": "recall",
                "question": f"Что означает {keyword}?",
                "answer": fact,
                "item_id": item.get("id", i),
                "hint": item.get("anchor", ""),
            })
        return tests

    def generate_definition_test(self, items: list[dict], count: int = 10) -> list[dict]:
        tests = []
        for i, item in enumerate(items):
            fact = item.get("fact", "")
            keyword = self._extract_keyword(fact)
            tests.append({
                "type": "definition",
                "question": f"Определите: {keyword}",
                "answer": fact,
                "item_id": item.get("id", i),
            })
        return tests[:count]

    def generate_association_test(self, items: list[dict], count: int = 10) -> list[dict]:
        tests = []
        for i, item in enumerate(items):
            anchor = item.get("anchor", "")
            tests.append({
                "type": "association",
                "question": "С каким звуком связана эта информация?",
                "answer": f"{anchor}",
                "item_id": item.get("id", i),
            })
        return tests[:count]

    def generate_fill_blank_test(self, items: list[dict], count: int = 10) -> list[dict]:
        tests = []
        for i, item in enumerate(items):
            fact = item.get("fact", "")
            words = fact.split()
            if not words:
                continue
            keyword = self._extract_keyword(fact)
            blanked = fact.replace(keyword, "____", 1) if keyword in fact else fact
            tests.append({
                "type": "fill_blank",
                "question": blanked,
                "answer": keyword,
                "item_id": item.get("id", i),
            })
        return tests[:count]

    def generate_full_test_suite(self, items: list[dict], tests_per_type: int = 5) -> dict:
        recall = self.generate_recall_test(items, tests_per_type)
        definition = self.generate_definition_test(items, tests_per_type)
        association = self.generate_association_test(items, tests_per_type)
        fill_blank = self.generate_fill_blank_test(items, tests_per_type)

        all_tests = recall + definition + association + fill_blank

        return {
            "tests": all_tests,
            "metadata": {
                "total": len(all_tests),
                "types": {
                    "recall": len(recall),
                    "definition": len(definition),
                    "association": len(association),
                    "fill_blank": len(fill_blank),
                },
                "created_at": datetime.now().isoformat(),
            },
        }

    def evaluate_answer(self, test_item: dict, user_answer: str) -> dict:
        correct = test_item.get("answer", "")
        user_clean = user_answer.lower().strip()
        correct_clean = correct.lower().strip()

        if user_clean == correct_clean:
            return {"is_correct": True, "similarity": 1.0, "correct_answer": correct}

        similarity = self._string_similarity(user_clean, correct_clean)
        return {
            "is_correct": similarity >= 0.5,
            "similarity": round(similarity, 3),
            "correct_answer": correct,
        }

    def save_test_suite(self, test_suite: dict, output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(test_suite, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_test_suite(self, input_path: str) -> dict:
        path = Path(input_path)
        return json.loads(path.read_text(encoding="utf-8"))

    def _extract_keyword(self, text: str) -> str:
        words = text.split()
        if not words:
            return ""
        capitalized = [w for w in words if w[0].isupper() and len(w) > 1]
        if capitalized:
            return capitalized[0].strip(".,;:!?\"'()[]")
        longest = max(words, key=len)
        return longest.strip(".,;:!?\"'()[]")

    def _string_similarity(self, a: str, b: str) -> float:
        set_a = set(a.split())
        set_b = set(b.split())
        if not set_a and not set_b:
            return 1.0
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)
