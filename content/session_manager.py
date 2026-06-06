"""Session manager for DreamStalker learning sessions."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4


@dataclass
class LearningGoal:
    topic: str
    description: str
    target_items_count: int = 20
    language: str = "ru"


@dataclass
class SleepSession:
    session_id: str
    goal: LearningGoal
    package_path: str = ""
    audio_path: str = ""
    test_path: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "prepared"


@dataclass
class TestResult:
    session_id: str
    item_id: str
    question: str
    correct_answer: str
    user_answer: str
    is_correct: bool
    response_time_sec: float


@dataclass
class SessionReport:
    session_id: str
    total_items: int
    correct: int
    incorrect: int
    accuracy: float
    weak_items: list = field(default_factory=list)
    strong_items: list = field(default_factory=list)


def _goal_to_dict(goal: LearningGoal) -> dict:
    return asdict(goal)


def _goal_from_dict(data: dict) -> LearningGoal:
    return LearningGoal(**data)


def _session_to_dict(session: SleepSession) -> dict:
    return {
        "session_id": session.session_id,
        "goal": _goal_to_dict(session.goal),
        "package_path": session.package_path,
        "audio_path": session.audio_path,
        "test_path": session.test_path,
        "created_at": session.created_at,
        "status": session.status,
    }


def _session_from_dict(data: dict) -> SleepSession:
    return SleepSession(
        session_id=data["session_id"],
        goal=_goal_from_dict(data["goal"]),
        package_path=data.get("package_path", ""),
        audio_path=data.get("audio_path", ""),
        test_path=data.get("test_path", ""),
        created_at=data.get("created_at", ""),
        status=data.get("status", "prepared"),
    )


class SessionManager:
    def __init__(self, base_path: str = "data/sessions"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _session_dir(self, session_id: str) -> Path:
        return self.base_path / session_id

    def create_session(self, goal: LearningGoal) -> SleepSession:
        session_id = uuid4().hex[:12]
        session = SleepSession(
            session_id=session_id,
            goal=goal,
            created_at=datetime.now().isoformat(),
        )
        session_dir = self._session_dir(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        meta = session_dir / "metadata.json"
        meta.write_text(json.dumps(_session_to_dict(session), ensure_ascii=False, indent=2))
        return session

    def save_package(self, session: SleepSession, items: list) -> None:
        session_dir = self._session_dir(session.session_id)
        pkg_path = session_dir / "package.json"
        pkg_path.write_text(json.dumps(items, ensure_ascii=False, indent=2))
        session.package_path = str(pkg_path)
        self._update_metadata(session)

    def save_audio(self, session: SleepSession, audio_path: str) -> None:
        session.audio_path = audio_path
        self._update_metadata(session)

    def save_test(self, session: SleepSession, test_items: list) -> None:
        session_dir = self._session_dir(session.session_id)
        test_path = session_dir / "test.json"
        test_path.write_text(json.dumps(test_items, ensure_ascii=False, indent=2))
        session.test_path = str(test_path)
        self._update_metadata(session)

    def load_session(self, session_id: str) -> SleepSession:
        meta = self._session_dir(session_id) / "metadata.json"
        data = json.loads(meta.read_text(encoding="utf-8"))
        return _session_from_dict(data)

    def get_session(self, session_id: str):
        try:
            return self.load_session(session_id)
        except Exception:
            return None

    def save_test_results(self, results, session_id: str = None) -> None:
        """Save test results to results.json.
        
        Args:
            results: Either a list of TestResult objects or a list of dicts.
            session_id: Optional session ID override (for CLI usage).
        """
        if not results:
            return
        
        # Support both list of TestResult objects and list of dicts
        if isinstance(results[0], TestResult):
            sid = results[0].session_id
            data = [asdict(r) for r in results]
        else:
            sid = session_id or results[0].get("session_id", "unknown")
            data = results
        
        session_dir = self._session_dir(sid)
        session_dir.mkdir(parents=True, exist_ok=True)
        results_path = session_dir / "results.json"
        results_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2)
        )

    def generate_report(self, session_id: str) -> SessionReport:
        results_path = self._session_dir(session_id) / "results.json"
        data = json.loads(results_path.read_text(encoding="utf-8"))
        total = len(data)
        correct = sum(1 for r in data if r["is_correct"])
        incorrect = total - correct
        accuracy = correct / total if total > 0 else 0.0

        item_stats: dict[str, dict] = {}
        for r in data:
            iid = r["item_id"]
            if iid not in item_stats:
                item_stats[iid] = {"correct": 0, "incorrect": 0, "question": r["question"]}
            if r["is_correct"]:
                item_stats[iid]["correct"] += 1
            else:
                item_stats[iid]["incorrect"] += 1

        weak = [
            {"item_id": k, "question": v["question"], "errors": v["incorrect"]}
            for k, v in item_stats.items() if v["incorrect"] > 0
        ]
        weak.sort(key=lambda x: x["errors"], reverse=True)

        strong = [
            {"item_id": k, "question": v["question"], "correct": v["correct"]}
            for k, v in item_stats.items() if v["incorrect"] == 0 and v["correct"] > 0
        ]
        strong.sort(key=lambda x: x["correct"], reverse=True)

        report = SessionReport(
            session_id=session_id,
            total_items=total,
            correct=correct,
            incorrect=incorrect,
            accuracy=round(accuracy, 4),
            weak_items=weak,
            strong_items=strong,
        )

        report_path = self._session_dir(session_id) / "report.json"
        report_path.write_text(json.dumps(asdict(report), ensure_ascii=False, indent=2))
        return report

    def list_sessions(self, status: str = None) -> list:
        sessions = []
        for meta_file in sorted(self.base_path.glob("*/metadata.json")):
            try:
                session = self.load_session(meta_file.parent.name)
                if status is None or session.status == status:
                    sessions.append(session)
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, FileNotFoundError):
                continue
        return sessions

    def _update_metadata(self, session: SleepSession) -> None:
        meta = self._session_dir(session.session_id) / "metadata.json"
        meta.write_text(json.dumps(_session_to_dict(session), ensure_ascii=False, indent=2))
