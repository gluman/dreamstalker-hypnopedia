from typing import Optional, List, Dict, Any
from .client import RAGFlowClient


class KnowledgeManager:
    DATASETS = {
        "personal": "Personal knowledge and experiences",
        "languages": "Language learning content",
        "skills": "Skills and abilities",
        "memories": "Memories to preserve",
        "vocabulary": "Vocabulary and definitions",
        "concepts": "Abstract concepts and ideas"
    }

    def __init__(self, client: RAGFlowClient):
        self.client = client
        self.dataset_map: Dict[str, str] = {}

    def setup_datasets(self) -> Dict[str, str]:
        existing = self.client.list_datasets()
        existing_names = {d.get("name"): d.get("id") for d in existing}

        for name, description in self.DATASETS.items():
            if name in existing_names:
                self.dataset_map[name] = existing_names[name]
            else:
                dataset_id = self.client.create_dataset(name, description)
                if dataset_id:
                    self.dataset_map[name] = dataset_id

        return self.dataset_map

    def get_dataset_id(self, topic: str) -> Optional[str]:
        self.dataset_map.setdefault(self.client.list_datasets())
        if not self.dataset_map:
            self.setup_datasets()

        topic_lower = topic.lower()
        if any(kw in topic_lower for kw in ["word", "vocab", "definition"]):
            return self.dataset_map.get("vocabulary")
        if any(kw in topic_lower for kw in ["language", "learn", "speak"]):
            return self.dataset_map.get("languages")
        if any(kw in topic_lower for kw in ["skill", "ability", "learn"]):
            return self.dataset_map.get("skills")
        if any(kw in topic_lower for kw in ["memory", "remember", "recall"]):
            return self.dataset_map.get("memories")
        return self.dataset_map.get("personal")

    def add_knowledge(self, topic: str, content: str) -> bool:
        dataset_id = self.get_dataset_id(topic)
        if not dataset_id:
            return False
        doc_id = self.client.add_document_content(dataset_id, content, title=topic)
        return doc_id is not None

    def search_knowledge(self, topic: str, query: str) -> List[Dict[str, Any]]:
        dataset_id = self.get_dataset_id(topic)
        if not dataset_id:
            return []
        return self.client.search(dataset_id, query)

    def get_knowledge_for_sleep(self, topic: str) -> List[str]:
        chunks = self.search_knowledge(topic, topic)
        return [chunk.get("content", "") for chunk in chunks if chunk.get("content")]

    def list_all_datasets(self) -> List[Dict[str, Any]]:
        return self.client.list_datasets()