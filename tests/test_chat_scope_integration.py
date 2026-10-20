"""Auxiliary discovery must stay inside the real Hermes credential scope."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERMES = os.environ.get("HERMES_AGENT_REPO", "")
pytestmark = pytest.mark.skipif(
    not HERMES or not (Path(HERMES) / "agent/secret_scope.py").is_file(),
    reason="Set HERMES_AGENT_REPO to a host supporting scoped secrets",
)


def test_auxiliary_discovery_isolates_credentials_endpoints_and_cache(tmp_path):
    home = tmp_path / "home"
    shutil.copytree(ROOT / "alibaba-token-plan",
                    home / "plugins/model-providers/alibaba-token-plan")
    env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
    env.update(HOME=str(tmp_path), HERMES_HOME=str(home),
               HERMES_MANAGED_DIR=str(tmp_path / "managed"), PYTHONPATH=HERMES,
               ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY="process-synthetic")
    probe = r'''
import socket
def blocked(*args, **kwargs):
    raise AssertionError("Scoped regression attempted network")
socket.socket.connect = blocked
socket.create_connection = blocked
from providers import get_provider_profile
from agent.secret_scope import set_secret_scope, reset_secret_scope, set_multiplex_active
profile = get_provider_profile('alibaba-token-plan')
assert profile is not None
calls = []
def fetch(self, *, api_key, base_url, **kwargs):
    assert api_key != 'process-synthetic', 'Borrowed process credentials'
    calls.append((api_key, base_url))
    if api_key == 'scope-b' and base_url == profile.base_url:
        return ['qwen3.6-flash']
    return ['deepseek-v4-flash-0731']
type(profile).fetch_models = fetch
set_multiplex_active(True)
def scoped(mapping):
    token = set_secret_scope(mapping)
    try:
        return profile.resolve_aux_model()
    finally:
        reset_secret_scope(token)
try:
    assert scoped({'ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY': 'scope-b'}) == 'qwen3.6-flash'
    assert scoped({'ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY': 'scope-c'}) == 'deepseek-v4-flash-0731'
    assert scoped({'ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY': 'scope-b'}) == 'qwen3.6-flash'
    assert len(calls) == 2, 'Cache mixed credentials or lost normal reuse'
    assert scoped({'ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY': 'scope-b',
                   'ALIBABA_TOKEN_PLAN_BASE_URL': 'https://example.invalid/v1'}) == 'deepseek-v4-flash-0731'
    assert len(calls) == 3, 'Cache mixed endpoints'
    assert scoped({}) == '', 'Empty scope borrowed process credentials/cache'
    assert profile.resolve_aux_model() == '', 'Unbound multiplexer borrowed credentials/cache'
    assert len(calls) == 3
finally:
    set_multiplex_active(False)
print('Scoped auxiliary discovery and cache: PASS')
'''
    result = subprocess.run([sys.executable, "-c", probe], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Scoped auxiliary discovery and cache: PASS" in result.stdout
