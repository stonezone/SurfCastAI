"""Helpers for managing OpenAI model configuration within the forecast engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(slots=True)
class ModelSettings:
    """Light-weight container describing how to call an OpenAI model."""

    name: str
    max_output_tokens: Optional[int]
    verbosity: Optional[str]
    reasoning_effort: Optional[str]

    @classmethod
    def from_config(cls, raw: Dict[str, Any], defaults: Optional[Dict[str, Any]] = None) -> "ModelSettings":
        """Create settings from loosely structured config data."""

        defaults = defaults or {}

        def pick(key: str) -> Any:
            if key in raw and raw[key] not in ("", None):
                return raw[key]
            return defaults.get(key)

        return cls(
            name=pick("name") or defaults.get("name", "gpt-5-nano"),
            max_output_tokens=pick("max_tokens"),
            verbosity=pick("verbosity"),
            reasoning_effort=pick("reasoning_effort"),
        )

    def into_response_kwargs(self) -> Dict[str, Any]:
        """Map the settings into keyword args understood by the Responses API."""

        kwargs: Dict[str, Any] = {"model": self.name}

        if self.max_output_tokens is not None:
            kwargs["max_output_tokens"] = int(self.max_output_tokens)

        if self.verbosity:
            kwargs["verbosity"] = self.verbosity

        if self.reasoning_effort:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}

        return kwargs

