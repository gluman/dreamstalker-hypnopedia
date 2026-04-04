"""DreamStalker structured logging module."""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional


class JSONFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_data"):
            entry.update(record.extra_data)
        return json.dumps(entry, ensure_ascii=False)


class DreamLogger:
    def __init__(self, log_dir="data/logs", session_id=None):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M")
        self._start_time = time.time()

        self._logger = logging.getLogger("dreamstalker." + self.session_id)
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()

        log_file = self.log_dir / (self.session_id + ".log")
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        self._logger.addHandler(fh)

        jsonl_file = self.log_dir / (self.session_id + ".jsonl")
        jh = logging.FileHandler(jsonl_file, encoding="utf-8")
        jh.setLevel(logging.DEBUG)
        jh.setFormatter(JSONFormatter())
        self._logger.addHandler(jh)

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(levelname)-8s | %(message)s"))
        self._logger.addHandler(ch)

    def _log(self, level, message, **kwargs):
        extra = {"extra_data": kwargs} if kwargs else {}
        self._logger.log(level, message, extra=extra)

    def info(self, message, **kwargs):
        self._log(logging.INFO, message, **kwargs)

    def error(self, message, **kwargs):
        self._log(logging.ERROR, message, **kwargs)

    def progress(self, step, current, total, message=""):
        pct = round(current / total * 100, 1) if total > 0 else 0
        msg = "[" + step + "] " + str(current) + "/" + str(total) + " (" + str(pct) + "%) " + message
        self._log(logging.INFO, msg.strip(), step=step, current=current, total=total, progress_pct=pct)

    def session_start(self, goal, items_count):
        self._start_time = time.time()
        self._log(logging.INFO, "Session started: " + goal + " (" + str(items_count) + " items)",
                  event="session_start", goal=goal, items_count=items_count, session_id=self.session_id)

    def session_end(self, session_id, status, duration):
        self._log(logging.INFO, "Session ended: " + session_id + " [" + status + "] in " + str(round(duration, 1)) + "s",
                  event="session_end", session_id=session_id, status=status, duration_sec=round(duration, 2))

    def audio_generated(self, path, duration_sec, size_kb):
        self._log(logging.INFO, "Audio generated: " + path + " (" + str(round(duration_sec, 1)) + "s, " + str(round(size_kb, 1)) + "KB)",
                  event="audio_generated", audio_path=path, duration_sec=round(duration_sec, 2), size_kb=round(size_kb, 1))

    def test_completed(self, session_id, score, total):
        self._log(logging.INFO, "Test completed: " + session_id + " score=" + str(score) + "% (" + str(total) + " questions)",
                  event="test_completed", session_id=session_id, score=score, total_questions=total)

    def get_session_logs(self, session_id):
        jsonl_path = self.log_dir / (session_id + ".jsonl")
        if not jsonl_path.exists():
            return []
        entries = []
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return entries
