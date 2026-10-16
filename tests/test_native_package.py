"""Native package acceptance; no shell installer or mocked admission.

HERMES_AGENT_REPO must point at Hermes v0.22.0+. The lifecycle tests require
Hermes's actual PM toolchain/dependency closure, in addition to import-time
Python dependencies. Prepare them with scripts/prepare-native-package-tests.py
and set HERMES_NATIVE_PACKAGE_SEED to its emitted seed. A missing toolchain is
a failure in native CI, not a skip. Linux also needs libseccomp; macOS uses
sandbox-exec. UV_OFFLINE is only a hint (upstream PM may strip it); the kernel
network guard remains authoritative for PM workers and compiled children.
HERMES_NATIVE_PACKAGE_DOWNLOADS=1 explicitly permits public PM dependency
downloads for lifecycle/pack only; these cases are then no-inference acceptance,
not offline. Python provider transports still have all sockets blocked.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERMES = os.environ.get("HERMES_AGENT_REPO", "")
pytestmark = pytest.mark.skipif(not HERMES, reason="Set HERMES_AGENT_REPO for real native package acceptance")


def run_native(tmp_path, scenario, component=""):
    guard = tmp_path / "guard"
    guard.mkdir()
    # Also guards capability-probe subprocesses. Never inherit operator keys,
    # proxies, Python startup hooks, configuration homes or package indexes.
    (guard / "sitecustomize.py").write_text('''
import socket

def blocked(*args, **kwargs):
    raise RuntimeError("offline native package test: external sockets blocked")
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
socket.create_connection = blocked
socket.getaddrinfo = blocked
''')
    home = tmp_path / "home"
    home.mkdir()
    downloads = scenario in {"lifecycle", "pack"} and os.environ.get("HERMES_NATIVE_PACKAGE_DOWNLOADS") == "1"
    seed = os.environ.get("HERMES_NATIVE_PACKAGE_SEED")
    if seed and scenario in {"lifecycle", "pack"}:
        # Seed only public tool artifacts and package-cache bytes, never an
        # operator home, config, credentials, install ledger or active venv.
        for folder in ("tools", "cache"):
            shutil.copytree(Path(seed) / folder, home / ".hermes" / folder,
                            symlinks=True)
    env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
    env.update(HOME=str(home), HERMES_HOME=str(home / ".hermes"),
               XDG_CACHE_HOME=str(home / ".cache"), TMPDIR=str(tmp_path),
               PYTHONPATH=os.pathsep.join([str(guard), HERMES, *sys.path]),
               PYTHONDONTWRITEBYTECODE="1", UV_OFFLINE="1",
               GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0", PIP_CONFIG_FILE=os.devnull,
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
               HERMES_NATIVE_PACKAGE_DOWNLOADS="1" if downloads else "0")
    prefix = []
    if sys.platform == "darwin" and not downloads:
        prefix = ["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"]
    result = subprocess.run(
        [*prefix, sys.executable, str(ROOT / "tests/helpers_native_package.py"),
         str(ROOT), scenario, component], cwd=tmp_path, env=env,
        capture_output=True, text=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("component", ["alibaba-token-plan", "alibaba-token-plan-media"])
def test_each_component_native_admission(tmp_path, component):
    run_native(tmp_path, "admission", component)


@pytest.mark.parametrize("component", ["alibaba-token-plan", "alibaba-token-plan-media"])
def test_each_component_native_lifecycle(tmp_path, component):
    run_native(tmp_path, "lifecycle", component)


def test_native_pack_namespace_and_partial_failure(tmp_path):
    run_native(tmp_path, "pack")


@pytest.mark.parametrize("component", ["flat", "category"])
def test_duplicate_shell_native_chat_import_refused(tmp_path, component):
    run_native(tmp_path, "collision", component)
