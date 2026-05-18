"""Central configuration loader — merges .env and settings.yaml."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent
load_dotenv(_project_root / ".env")


def _load_settings_yaml() -> dict:
    """Load config/settings.yaml if it exists."""
    settings_path = _project_root / "config" / "settings.yaml"
    if settings_path.exists():
        with open(settings_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


_settings_cache: Optional[dict] = None


def get_settings() -> dict:
    """Get merged settings: .env overrides settings.yaml."""
    global _settings_cache
    if _settings_cache is not None:
        return _settings_cache

    yaml_cfg = _load_settings_yaml()

    # Merge: .env takes precedence
    merged = {
        "ragflow": {
            "base_url": os.getenv("RAGFLOW_BASE_URL", yaml_cfg.get("ragflow", {}).get("base_url", "http://localhost:9380")),
            "api_key": os.getenv("RAGFLOW_API_KEY", yaml_cfg.get("ragflow", {}).get("api_key", "")),
            "dataset_id": os.getenv("RAGFLOW_DATASET_ID", yaml_cfg.get("ragflow", {}).get("dataset_id", "")),
        },
        "audio": yaml_cfg.get("audio", {}),
        "sleep_phases": yaml_cfg.get("sleep_phases", {}),
        "tmr": yaml_cfg.get("tmr", {}),
        "paths": yaml_cfg.get("paths", {}),
        "data_dir": os.getenv("DATA_DIR", yaml_cfg.get("data_dir", "data")),
        "audio_dir": os.getenv("AUDIO_DIR", yaml_cfg.get("audio", {}).get("output_dir", "data/audio")),
    }

    _settings_cache = merged
    return merged


def get_ragflow_config() -> dict:
    """Get RAGFlow connection config."""
    cfg = get_settings()
    rf = cfg["ragflow"]
    return {
        "base_url": rf["base_url"],
        "api_key": rf["api_key"],
        "dataset_id": rf["dataset_id"],
    }


def reload_settings():
    """Clear settings cache (useful for testing)."""
    global _settings_cache
    _settings_cache = None
