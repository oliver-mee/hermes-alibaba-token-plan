"""Test fixtures for the token-plan provider plugins.

Mocks the ``providers`` package before tests import the plugin modules, so
the suite runs standalone without a Hermes agent checkout installed. The
mock ``ProviderProfile`` mirrors the field names of the real dataclass in
``providers/base.py`` — if a field here drifts from upstream, the plugin
would fail the same way at real discovery time.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from urllib.parse import urlparse

import pytest


@dataclass
class MockProviderProfile:
    name: str = ""
    api_mode: str = "chat_completions"
    aliases: tuple = ()
    display_name: str = ""
    description: str = ""
    signup_url: str = ""
    env_vars: tuple = ()
    base_url: str = ""
    models_url: str = ""
    auth_type: str = "api_key"
    supports_health_check: bool = True
    supports_vision: bool = False
    supports_vision_tool_messages: bool = True
    supports_prompt_cache_key: bool = False
    fallback_models: tuple = ()
    hostname: str = ""
    default_headers: dict = field(default_factory=dict)
    fixed_temperature: object = None
    default_max_tokens: int | None = None
    default_aux_model: str = ""

    def get_hostname(self) -> str:
        if self.hostname:
            return self.hostname
        if self.base_url:
            return urlparse(self.base_url).hostname or ""
        return ""

    def fetch_models(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 8.0,
    ) -> list[str] | None:
        return None

    def resolve_aux_model(self, *, vision: bool = False) -> str:
        """Upstream default: no live answer, caller keeps default_aux_model."""
        return ""


REGISTERED: dict[str, MockProviderProfile] = {}


def _register_provider(profile: MockProviderProfile) -> None:
    REGISTERED[profile.name] = profile


@pytest.fixture(autouse=True)
def mock_providers_package(monkeypatch):
    """Install mock ``providers`` / ``providers.base`` modules and clear state."""
    REGISTERED.clear()

    providers_mod = types.ModuleType("providers")
    providers_mod.register_provider = _register_provider

    base_mod = types.ModuleType("providers.base")
    base_mod.ProviderProfile = MockProviderProfile
    providers_mod.base = base_mod

    monkeypatch.setitem(sys.modules, "providers", providers_mod)
    monkeypatch.setitem(sys.modules, "providers.base", base_mod)

    # Force re-import of the plugin modules under the mocked package
    for key in list(sys.modules):
        if key.startswith("_test_token_plan_plugin"):
            del sys.modules[key]

    yield REGISTERED
