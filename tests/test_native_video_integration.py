"""Real Hermes discovery and dispatcher, synthetic keys and mocked HTTP only."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERMES = os.environ.get("HERMES_AGENT_REPO", "")
pytestmark = pytest.mark.skipif(not HERMES, reason="Set HERMES_AGENT_REPO for native discovery/dispatch")


def test_native_plugin_install_discovery_dispatch(tmp_path):
    home = tmp_path / "hermes"
    # A tightly selected environment prevents loading the operator's credentials/config.
    env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
    env.update(HERMES_HOME=str(home), HOME=str(tmp_path), PYTHONPATH=os.pathsep.join([HERMES, *sys.path]),
               HERMES_NATIVE_TEST="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    installed = subprocess.run(["bash", str(ROOT / "install.sh")], env=env, capture_output=True, text=True)
    assert installed.returncode == 0, installed.stderr
    (home / "config.yaml").write_text("plugins:\n  enabled: [video_gen/alibaba-token-plan-video]\nvideo_gen:\n  provider: alibaba-token-plan\n  model: happyhorse-1.1-t2v\n")
    probe = '''
import socket
def blocked(*args, **kwargs):
    raise AssertionError("Offline discovery attempted a socket connection")
socket.socket.connect = blocked
socket.create_connection = blocked
from hermes_cli.plugins import PluginManager
from agent import video_gen_registry
manager = PluginManager()
manager.discover_and_load()
provider = video_gen_registry.get_provider("alibaba-token-plan")
assert provider is not None, "Native plugin not discovered"
assert len(provider.list_models()) == 4
assert not provider.is_available(), "Synthetic test home must have no credentials"
assert provider.generate("A cloud")["error_type"] == "missing_credentials"
from tools.video_generation_tool import _handle_video_generate
import json
assert json.loads(_handle_video_generate({"prompt": "A cloud"}))["error_type"] == "missing_credentials"
'''
    result = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    result = subprocess.run([sys.executable, "-m", "pytest", str(ROOT / "tests/test_native_video.py"), "-q"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
