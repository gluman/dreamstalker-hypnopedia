"""Service layer — единая точка инициализации компонентов для CLI и Web.

Использует core.config для загрузки настроек из .env + settings.yaml.
"""

from pathlib import Path
from typing import Optional

from content.session_manager import SessionManager
from content.package_builder import PackageBuilder
from content.test_generator import TestGenerator
from content.anchor_generator import AnchorGenerator
from core.audio_generator import NightAudioGenerator, NightConfig
from core.config import get_ragflow_config, get_settings
from core.logger import DreamLogger


class ServiceContainer:
    """Lazy-initialized container of all services used by CLI and Web.

    Both main.py and web/app.py should call `ServiceContainer()` once
    and reuse the same instances instead of constructing duplicates.
    """

    def __init__(self):
        self._sm: Optional[SessionManager] = None
        self._pb: Optional[PackageBuilder] = None
        self._tg: Optional[TestGenerator] = None
        self._ag: Optional[AnchorGenerator] = None
        self._ng: Optional[NightAudioGenerator] = None
        self._logger: Optional[DreamLogger] = None

    @property
    def session_manager(self) -> SessionManager:
        if self._sm is None:
            settings = get_settings()
            self._sm = SessionManager(base_path=settings.get("data_dir", "data/sessions"))
        return self._sm

    @property
    def package_builder(self) -> PackageBuilder:
        if self._pb is None:
            self._pb = PackageBuilder()
        return self._pb

    @property
    def test_generator(self) -> TestGenerator:
        if self._tg is None:
            self._tg = TestGenerator()
        return self._tg

    @property
    def anchor_generator(self) -> AnchorGenerator:
        if self._ag is None:
            self._ag = AnchorGenerator()
        return self._ag

    @property
    def night_audio_generator(self) -> NightAudioGenerator:
        if self._ng is None:
            self._ng = NightAudioGenerator(NightConfig())
        return self._ng

    @property
    def logger(self) -> DreamLogger:
        if self._logger is None:
            self._logger = DreamLogger()
        return self._logger

    @property
    def ragflow_config(self) -> dict:
        return get_ragflow_config()

    @property
    def sessions_dir(self) -> Path:
        return Path(get_settings().get("data_dir", "data/sessions"))
