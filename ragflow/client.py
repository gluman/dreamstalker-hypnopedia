import requests
from typing import Optional, List, Dict, Any


class RAGFlowClient:
    def __init__(self, base_url: str = "http://192.168.0.156:9380", api_key: str = "ragflow-UJmyXeAW4Eb6OcWNCxc8oq_Q92CTUbZWGtz2hXHqRq8"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.api_base = f"{self.base_url}/api/v1"

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.api_base}{endpoint}"
        response = requests.request(method, url, headers=self.headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def create_dataset(self, name: str, description: str = "") -> Optional[str]:
        data = {"name": name, "description": description}
        result = self._request("POST", "/datasets", json=data)
        return result.get("data", {}).get("id")

    def upload_document(self, dataset_id: str, file_path: str) -> Optional[str]:
        url = f"{self.api_base}/datasets/{dataset_id}/documents"
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, headers={"Authorization": f"Bearer {self.api_key}"}, files=files)
        response.raise_for_status()
        result = response.json()
        return result.get("data", {}).get("id")

    def list_datasets(self) -> List[Dict[str, Any]]:
        result = self._request("GET", "/datasets")
        return result.get("data", [])

    def get_dataset(self, dataset_id: str) -> Dict[str, Any]:
        result = self._request("GET", f"/datasets/{dataset_id}")
        return result.get("data", {})

    def create_chat(self, dataset_id: str, question: str) -> str:
        chat_data = {
            "dataset_id": dataset_id,
            "question": question,
            "mode": "accurate"
        }
        result = self._request("POST", "/chats", json=chat_data)
        chat_id = result.get("data", {}).get("id")
        if not chat_id:
            return ""
        completion = self._request("POST", f"/chats/{chat_id}/completions", json={"question": question})
        return completion.get("data", {}).get("answer", "")

    def chat(self, dataset_id: str, question: str) -> str:
        return self.create_chat(dataset_id, question)

    def search(self, dataset_id: str, query: str) -> List[Dict[str, Any]]:
        data = {"question": query}
        result = self._request("POST", f"/datasets/{dataset_id}/search", json=data)
        return result.get("data", {}).get("chunks", [])

    def delete_dataset(self, dataset_id: str) -> bool:
        self._request("DELETE", f"/datasets/{dataset_id}")
        return True

    def add_document_content(self, dataset_id: str, content: str, title: str = "Untitled") -> Optional[str]:
        url = f"{self.api_base}/datasets/{dataset_id}/documents"
        files = {"file": (f"{title}.txt", content.encode(), "text/plain")}
        response = requests.post(url, headers={"Authorization": f"Bearer {self.api_key}"}, files=files)
        response.raise_for_status()
        result = response.json()
        return result.get("data", {}).get("id")