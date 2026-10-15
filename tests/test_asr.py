"""Offline wire and validation tests; real Hermes contracts run in a subprocess."""
import base64
import importlib.util
import io
import sys
import types
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def asr(monkeypatch):
    modules = {
        "agent": types.ModuleType("agent"),
        "agent.secret_scope": types.SimpleNamespace(get_secret=lambda key: "synthetic"),
        "agent.transcription_provider": types.SimpleNamespace(TranscriptionProvider=type("Base", (), {
            "default_model": lambda self: self.list_models()[0]["id"]})),
        "tools": types.ModuleType("tools"),
        "tools.transcription_audio": types.SimpleNamespace(_find_ffmpeg_binary=lambda: None, _find_ffprobe_binary=lambda: None),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("asr_test", ROOT / "alibaba-token-plan-asr/provider.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wav(seconds=1, rate=16000):
    result = io.BytesIO()
    with wave.open(result, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"\0\0" * int(seconds * rate))
    return result.getvalue()


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "voice.wav"
    path.write_bytes(wav())
    return path


def test_payload_and_silence(asr, audio, monkeypatch):
    calls = []
    def post(payload, key):
        calls.append(payload)
        return {"output": {"text": ""}}
    monkeypatch.setattr(asr, "post", post)
    result = asr.TokenPlanASR().transcribe(str(audio))
    assert result == {"success": True, "transcript": "", "provider": "alibaba-token-plan-asr"}
    payload = calls[0]
    assert payload["model"] == "qwen-audio-3.0-asr-flash"
    assert payload["parameters"] == {"format": "wav", "sample_rate": "16000"}
    data = payload["input"]["messages"][0]["content"][0]["input_audio"]["data"]
    assert base64.b64decode(data.split(",")[1]) == audio.read_bytes()


@pytest.mark.parametrize("kwargs", [{"model": "other"}, {"language": "en"}, {"prompt": "hint"}])
def test_unsupported_options_never_submit(asr, audio, monkeypatch, kwargs):
    monkeypatch.setattr(asr, "post", lambda *args: pytest.fail("HTTP must not run"))
    assert not asr.TokenPlanASR().transcribe(str(audio), **kwargs)["success"]


@pytest.mark.parametrize("kind", ["empty", "symlink", "directory", "fifo", "large", "long", "truncated", "bad"])
def test_unsafe_inputs(asr, tmp_path, monkeypatch, kind):
    import os
    path = tmp_path / "audio"
    if kind == "symlink":
        path.symlink_to(tmp_path / "missing")
    elif kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "large":
        with path.open("wb") as f:
            f.truncate(asr.MAX_SOURCE + 1)
    else:
        path.write_bytes({"empty": b"", "long": wav(181), "truncated": wav()[:100], "bad": b"invalid"}[kind])
    monkeypatch.setattr(asr, "post", lambda *args: pytest.fail("HTTP must not run"))
    result = asr.TokenPlanASR().transcribe(str(path))
    assert not result["success"]
    assert str(tmp_path) not in result["error"]


@pytest.mark.parametrize("payload,text", [({"output": {"text": " hello "}}, "hello"),
    ({"output": {"output": {"sentence": {"text": "你好"}}}}, "你好")])
def test_extract(asr, payload, text):
    assert asr.extract_transcript(payload) == text


def test_missing_and_scoped_credentials(asr, audio, monkeypatch):
    requested = []
    def get(key):
        requested.append(key)
        return None
    monkeypatch.setattr(asr, "get_secret", get)
    assert not asr.TokenPlanASR().is_available()
    assert "Set ALIBABA" in asr.TokenPlanASR().transcribe(str(audio))["error"]
    assert set(requested) == set(asr.KEYS)
    assert not any("TEAM" in key or "CN" in key or "DASHSCOPE" in key for key in requested)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 302])
def test_http_errors_sanitised_and_not_retried(asr, monkeypatch, status):
    calls = []
    class Response:
        def read(self, limit): return b'{"message":"private-key-and-path"}'
    Response.status = status
    class Connection:
        def __init__(self, host, timeout):
            assert host == "token-plan.maas.qwencloudapi.com"
            assert timeout == 60
        def request(self, method, route, **kwargs): calls.append((method, route))
        def getresponse(self): return Response()
        def close(self): pass
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    with pytest.raises(asr.ASRError, match=f"HTTP {status}") as error:
        asr.post({}, "synthetic")
    assert "private" not in str(error.value)
    assert calls == [("POST", asr.ROUTE)]


def test_bad_response(asr):
    for payload in ({}, {"output": {}}, {"output": {"text": 4}}):
        with pytest.raises(asr.ASRError):
            asr.extract_transcript(payload)


def test_successful_http_payload_and_close(asr, monkeypatch):
    calls = []
    class Connection:
        def __init__(self, *a, **kw): pass
        def request(self, *args, **kwargs): calls.append(kwargs)
        def getresponse(self):
            return types.SimpleNamespace(status=200, read=lambda limit: b'{"output":{"text":"hi"}}')
        def close(self): calls.append("closed")
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    assert asr.post({"model": "test"}, "synthetic")["output"]["text"] == "hi"
    assert calls[0]["headers"]["X-DashScope-SSE"] == "disable"
    assert calls[-1] == "closed"


@pytest.mark.parametrize("raw", [b"not JSON private-key", b'{"code":"private-key"}', b"x" * (1024 * 1024 + 1)])
def test_malformed_upstream_never_leaks(asr, audio, monkeypatch, raw):
    class Connection:
        def __init__(self, *a, **kw): pass
        def request(self, *a, **kw): pass
        def getresponse(self): return types.SimpleNamespace(status=200, read=lambda limit: raw)
        def close(self): pass
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    result = asr.TokenPlanASR().transcribe(str(audio))
    assert not result["success"]
    assert "private-key" not in result["error"]


def test_legacy_first_key_and_unknown_extra(asr, audio, monkeypatch):
    monkeypatch.setattr(asr, "get_secret", lambda key: key)
    captured = []
    def post(payload, key):
        captured.append(key)
        return {"output": {"text": "ok"}}
    monkeypatch.setattr(asr, "post", post)
    assert asr.TokenPlanASR().transcribe(str(audio), future_option="ignored")["success"]
    assert captured == [asr.KEYS[0]]


def test_old_host_registration_does_not_import_native_api(caplog):
    spec = importlib.util.spec_from_file_location("old_host_asr", ROOT / "alibaba-token-plan-asr/__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.register(object())
    assert "requires Hermes >=0.22.0" in caplog.text
