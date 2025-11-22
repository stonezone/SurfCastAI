"""JSON prompt loader for SurfCastAI."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional


class PromptLoader:
    """Load structured prompts from versioned JSON templates."""

    REQUIRED_FIELDS = {"system_prompt", "user_prompt_template"}

    def __init__(
        self,
        base_dir: Optional[str],
        *,
        version: Optional[str] = "v1",
        logger: Optional[logging.Logger] = None,
        fallback_provider: Optional[Callable[[], Dict[str, Dict]]] = None,
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir else None
        self.version = version
        self.logger = logger or logging.getLogger("utils.prompt_loader")
        self._fallback_provider = fallback_provider
        self._prompts: Dict[str, Dict] = {}
        self._fallback_active = False
        self.reload()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def reload(self) -> None:
        """Reload prompt files from disk, falling back when necessary."""
        loaded: Dict[str, Dict] = {}

        version_dir = self._resolve_version_dir()
        if version_dir and version_dir.exists():
            for prompt_path in sorted(version_dir.glob("*.json")):
                prompt = self._load_prompt_file(prompt_path)
                if prompt is None:
                    continue
                name = prompt.get("name") or prompt_path.stem
                loaded[name] = prompt

        if loaded:
            self._prompts = loaded
            self._fallback_active = False
        else:
            self._activate_fallback()

    def has_prompt(self, name: str) -> bool:
        return name in self._prompts

    def get_prompt(self, name: str) -> Dict:
        return self._prompts[name]

    def available_prompts(self) -> Iterable[str]:
        return self._prompts.keys()

    def is_fallback_enabled(self) -> bool:
        return self._fallback_active

    def as_templates(self, aliases: Optional[Dict[str, str]] = None) -> Dict[str, Dict]:
        """Return prompts mapped for PromptTemplates consumption."""
        mapping: Dict[str, Dict] = {}
        for name, prompt in self._prompts.items():
            mapping[name] = prompt
            if aliases and name in aliases:
                mapping[aliases[name]] = prompt
        return mapping

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _resolve_version_dir(self) -> Optional[Path]:
        if self.base_dir is None:
            return None
        if self.version:
            return self.base_dir / self.version
        return self.base_dir

    def _load_prompt_file(self, path: Path) -> Optional[Dict]:
        try:
            data = json.loads(path.read_text())
        except Exception as error:  # broad: json + IO
            self.logger.warning("Failed to load prompt %s: %s", path.name, error)
            return None

        if not self._is_valid_prompt(data):
            self.logger.warning("Invalid prompt file skipped: %s", path.name)
            return None

        return data

    def _is_valid_prompt(self, prompt: Dict) -> bool:
        return all(field in prompt for field in self.REQUIRED_FIELDS)

    def _activate_fallback(self) -> None:
        fallback_prompts = self._fallback_provider() if self._fallback_provider else None
        if fallback_prompts:
            self._prompts = dict(fallback_prompts)
            self._fallback_active = True
        else:
            self._prompts = {}
            self._fallback_active = False

