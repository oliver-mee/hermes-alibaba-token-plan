"""Real Hermes plugin discovery, tool dispatch and profile isolation, offline only."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERMES = os.environ.get("HERMES_AGENT_REPO", "")
pytestmark = pytest.mark.skipif(not HERMES, reason="Set HERMES_AGENT_REPO to Hermes v0.22.0+ for native image dispatch")


def test_native_registration_dispatch_and_profiles(tmp_path):
    home = tmp_path / "hermes"
    env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
    env.update(HOME=str(tmp_path), HERMES_HOME=str(home), PYTHONPATH=os.pathsep.join([HERMES, *sys.path]),
               PYTEST_DISABLE_PLUGIN_AUTOLOAD="1", HERMES_NATIVE_TEST="1")
    installed = subprocess.run(["bash", str(ROOT / "install.sh")], env=env, text=True,
                               capture_output=True, timeout=30)
    assert installed.returncode == 0, installed.stderr
    config = ("plugins:\n  enabled: [image_gen/alibaba-token-plan-image]\n"
              "image_gen:\n  provider: alibaba-token-plan\n  model: wan2.7-image\n")
    (home / "config.yaml").write_text(config)
    probe = r'''
import base64
import contextvars
import http.client
import json
from pathlib import Path
import socket
from concurrent.futures import ThreadPoolExecutor

def blocked(*args, **kwargs):
    raise AssertionError("Offline integration attempted a socket connection")
socket.socket.connect = blocked
socket.create_connection = blocked

from hermes_cli.plugins import PluginManager
from agent import image_gen_registry
from agent.secret_scope import set_secret_scope, reset_secret_scope, set_multiplex_active
from hermes_constants import get_hermes_home, set_hermes_home_override, reset_hermes_home_override
manager = PluginManager()
manager.discover_and_load()
p = image_gen_registry.get_provider("alibaba-token-plan")
assert p is not None, "Native image plugin not discovered"
assert len(p.list_models()) == 2
assert len(image_gen_registry.get_provider("alibaba-token-plan-team").list_models()) == 4
assert not p.is_available(), "Synthetic home must have no credentials"

from tools.image_generation_tool import _handle_image_generate, _build_dynamic_image_schema
missing = json.loads(_handle_image_generate({"prompt": "cloud"}))
assert missing["error_type"] == "missing_credentials", missing
assert "image_url" in _build_dynamic_image_schema()["parameters"]["properties"]

png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6d8sAAAAASUVORK5CYII=")
calls = []
url = "https://example.com/image.png"
class Response:
    status = 200
    def __init__(self, data): self.raw = json.dumps(data).encode()
    def read(self, cap):
        chunk, self.raw = self.raw[:cap], self.raw[cap:]
        return chunk
class Connection:
    def __init__(self, host, timeout): self.host = host
    def request(self, method, path, body=None, headers=None):
        self.method = method
        self.asynchronous = bool(headers.get("X-DashScope-Async"))
        calls.append((self.host, method, path, json.loads(body) if body else None, headers))
    def getresponse(self):
        if self.method == "POST" and self.asynchronous:
            return Response({"output": {"task_id": "synthetic-job"}})
        return Response({"output": {"task_status": "SUCCEEDED", "choices": [
            {"message": {"content": [{"image": url}]}}]}})
    def close(self): pass
http.client.HTTPSConnection = Connection

import tools.url_safety as safety
class MediaResponse:
    status_code = 200
    headers = {"content-type": "image/png"}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def iter_bytes(self, **kwargs): return iter([png])
class MediaClient:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def stream(self, method, target):
        assert method == "GET" and target == url
        return MediaResponse()
safety.create_ssrf_safe_client = lambda **kwargs: MediaClient()
socket.getaddrinfo = lambda *a, **kw: [(0, 0, 0, "", ("93.184.216.34", 443))]

token = set_secret_scope({"ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY": "synthetic-profile-key"})
try:
    result = json.loads(_handle_image_generate({"prompt": "cloud", "aspect_ratio": "square"}))
    assert result["success"], result
    assert Path(result["image"]).read_bytes() == png
    assert Path(result["image"]).is_relative_to(get_hermes_home())
    assert len(calls) == 2 and calls[0][1] == "POST" and calls[1][1] == "GET"
    assert calls[0][4]["X-DashScope-Async"] == "enable"
    # Normal image_url/reference_image_urls dispatch: keep selected Wan non-Pro.
    inline = "data:image/png;base64," + base64.b64encode(png).decode()
    edited = json.loads(_handle_image_generate({"prompt": "Make blue", "image_url": inline,
                                                "reference_image_urls": [inline]}))
    assert edited["success"] and edited["modality"] == "image", edited
    assert calls[-2][3]["model"] == "wan2.7-image"
    assert len(calls[-2][3]["input"]["messages"][0]["content"]) == 3
finally:
    reset_secret_scope(token)

# The other model family must use its synchronous contract through the same tool.
own_home = get_hermes_home()
config_path = own_home / "config.yaml"
original_config = config_path.read_text()
config_path.write_text("plugins:\n  enabled: [image_gen/alibaba-token-plan-image]\n"
                       "image_gen:\n  provider: alibaba-token-plan-team\n  model: qwen-image-2.0\n")
token = set_secret_scope({"ALIBABA_TOKEN_PLAN_TEAM_API_KEY": "synthetic-team-key"})
try:
    before = len(calls)
    for args in ({"prompt": "cloud"}, {"prompt": "make blue", "image_url": inline}):
        result = json.loads(_handle_image_generate(args))
        assert result["success"] and result["model"] == "qwen-image-2.0", result
        assert result["task_id"] is None
    assert len(calls) == before + 2
    assert all(c[1] == "POST" and c[2].endswith("multimodal-generation/generation")
               and "X-DashScope-Async" not in c[4] for c in calls[before:])
finally:
    reset_secret_scope(token)
    config_path.write_text(original_config)

own_home = get_hermes_home()
profile_a, profile_b = own_home / "profile-a", own_home / "profile-b"
for home in (profile_a, profile_b):
    home.mkdir()
    (home / "config.yaml").write_text("image_gen:\n  provider: alibaba-token-plan\n  model: wan2.7-image\n")
set_multiplex_active(True)
try:
    # In multiplex mode process-global credentials may never act as a fallback.
    assert not p.is_available()
    def generate_for(home, key):
        ht = set_hermes_home_override(home)
        st = set_secret_scope({"ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY": key})
        try:
            result = p.generate("cloud")
            assert result["success"], result
            path = Path(result["image"])
            assert path.is_relative_to(home) and path.read_bytes() == png
            return str(path)
        finally:
            reset_secret_scope(st)
            reset_hermes_home_override(ht)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(generate_for, profile_a, "synthetic-key-a")
        b = pool.submit(generate_for, profile_b, "synthetic-key-b")
        assert a.result() != b.result()
    assert {c[4]["Authorization"] for c in calls if c[1] == "POST"} >= {
        "Bearer synthetic-key-a", "Bearer synthetic-key-b"}
finally:
    set_multiplex_active(False)
print("Native image discovery/dispatch/profile isolation: PASS")
'''
    result = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env,
                            text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Native image discovery/dispatch/profile isolation: PASS" in result.stdout
    # Reuse the same wire/safety suite against the real native ABC and secret API.
    result = subprocess.run([sys.executable, "-m", "pytest", str(ROOT / "tests/test_native_image.py"), "-q"],
                            cwd=tmp_path, env=env, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
