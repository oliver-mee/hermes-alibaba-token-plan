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

@pytest.mark.parametrize("name", ["alibaba-token-plan-asr", "alibaba-token-plan-team-asr",
                                  "alibaba-token-plan-cn-asr", "alibaba-token-plan-cn-team-asr"])
def test_all_listed_asr_accounts_are_isolated(asr, audio, monkeypatch, name):
    provider = asr.TokenPlanASR(name)
    requested, calls = [], []
    def secret(key):
        requested.append(key)
        return "synthetic" if key == provider.keys[-1] else ""
    monkeypatch.setattr(asr, "get_secret", secret)
    monkeypatch.setattr(asr, "post", lambda *args: calls.append(args) or {"output": {"text": "ok"}})
    assert provider.transcribe(audio)["success"]
    assert requested == list(provider.keys)
    assert len(calls) == 1
    assert (calls[0][2] if len(calls[0]) == 3 else "token-plan.maas.qwencloudapi.com") == provider.host
    assert provider.get_setup_schema()["env_vars"][0]["key"] == provider.keys[-1]
    monkeypatch.setattr(asr, "get_secret", lambda key: "other-account" if key not in provider.keys else "")
    assert not provider.is_available()
    assert provider.transcribe(audio)["error_kind"] == "credential"
    assert len(calls) == 1



@pytest.fixture
def asr(monkeypatch):
    modules = {
        "agent": types.ModuleType("agent"),
        "agent.secret_scope": types.SimpleNamespace(get_secret=lambda key: "synthetic"),
        "agent.file_safety": types.SimpleNamespace(get_read_block_error=lambda path: None),
        "agent.transcription_provider": types.SimpleNamespace(TranscriptionProvider=type("Base", (), {
            "default_model": lambda self: self.list_models()[0]["id"]})),
        "tools": types.ModuleType("tools"),
        "tools.transcription_audio": types.SimpleNamespace(_find_ffmpeg_binary=lambda: None, _find_ffprobe_binary=lambda: None),
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("asr_test", ROOT / "alibaba-token-plan-media/asr/provider.py")
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
    def post(payload, key, host):
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
            return types.SimpleNamespace(status=200, read=io.BytesIO(b'{"output":{"text":"hi"}}').read)
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
        def getresponse(self): return types.SimpleNamespace(status=200, read=io.BytesIO(raw).read)
        def close(self): pass
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    result = asr.TokenPlanASR().transcribe(str(audio))
    assert not result["success"]
    assert "private-key" not in result["error"]


def test_legacy_first_key_and_unknown_extra(asr, audio, monkeypatch):
    monkeypatch.setattr(asr, "get_secret", lambda key: key)
    captured = []
    def post(payload, key, host):
        captured.append(key)
        return {"output": {"text": "ok"}}
    monkeypatch.setattr(asr, "post", post)
    assert asr.TokenPlanASR().transcribe(str(audio), future_option="ignored")["success"]
    assert captured == [asr.KEYS[0]]


def test_old_host_registration_does_not_import_native_api(caplog):
    spec = importlib.util.spec_from_file_location("old_host_asr", ROOT / "alibaba-token-plan-media/asr/__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.register(object())
    assert "requires Hermes >=0.22.0" in caplog.text


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    import socket
    def deny(*args, **kwargs):
        pytest.fail("Network forbidden in offline ASR tests")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


def test_native_metadata_and_availability_are_offline(asr, monkeypatch):
    provider = asr.TokenPlanASR()
    assert provider.display_name == provider.get_setup_schema()["name"]
    assert provider.default_model() == "qwen-audio-3.0-asr-flash"
    assert [row["id"] for row in provider.list_models()] == [provider.default_model()]
    assert provider.is_available()
    monkeypatch.setattr(asr, "get_secret", lambda key: (_ for _ in ()).throw(RuntimeError("private")))
    assert not provider.is_available()


def test_missing_key_does_not_read_or_decode(asr, monkeypatch):
    monkeypatch.setattr(asr, "get_secret", lambda key: None)
    monkeypatch.setattr(asr, "normalise", lambda path: pytest.fail("Must resolve key before reading audio"))
    result = asr.TokenPlanASR().transcribe("missing")
    assert result["error_kind"] == "credential"


@pytest.mark.parametrize("data", [wav()[:100], wav(181)])
def test_invalid_pcm_never_enters_repair_decoder(asr, tmp_path, monkeypatch, data):
    path = tmp_path / "recording.wav"
    path.write_bytes(data)
    monkeypatch.setattr(asr, "_find_ffmpeg_binary", lambda: pytest.fail("Must reject damaged/long PCM"))
    assert asr.TokenPlanASR().transcribe(path)["error_kind"] == "invalid_request"


@pytest.mark.parametrize("failure", ["probe", "decode", "cancel", "duration", "truncated"])
def test_conversion_cleanup_and_bounds(asr, audio, tmp_path, monkeypatch, failure):
    import subprocess
    audio.write_bytes(wav(rate=8000))
    monkeypatch.setattr(asr, "_find_ffmpeg_binary", lambda: "ffmpeg")
    monkeypatch.setattr(asr, "_find_ffprobe_binary", lambda: "ffprobe")
    monkeypatch.setattr(asr.tempfile, "tempdir", str(tmp_path))
    calls = []
    def run(command, **options):
        calls.append(command)
        assert options["stdin"] == subprocess.DEVNULL
        assert command[command.index("-protocol_whitelist") + 1] == "file"
        assert command[command.index("-format_whitelist") + 1] == asr.DEMUXERS
        assert "concat" not in asr.DEMUXERS and "hls" not in asr.DEMUXERS
        if command[0] == "ffprobe":
            assert options["timeout"] == 15
            if failure == "probe":
                raise subprocess.TimeoutExpired(command, 15)
            return types.SimpleNamespace(stdout=b'{"format":{"duration":"1"}}')
        assert options["timeout"] == 30 and "-xerror" in command
        assert command[command.index("-t") + 1] == "181"
        assert command[command.index("-fs") + 1] == str(asr.MAX_WAV)
        if failure == "cancel":
            raise KeyboardInterrupt()
        if failure == "decode":
            raise subprocess.CalledProcessError(1, command, stderr=b"private-path")
        Path(command[-1]).write_bytes(wav(181) if failure == "duration" else wav()[:100])
    monkeypatch.setattr(asr.subprocess, "run", run)
    monkeypatch.setattr(asr, "post", lambda *args: pytest.fail("Must not upload"))
    original = audio.read_bytes()
    if failure == "cancel":
        with pytest.raises(KeyboardInterrupt):
            asr.TokenPlanASR().transcribe(audio)
    else:
        result = asr.TokenPlanASR().transcribe(audio)
        assert not result["success"] and "private" not in result["error"]
        assert result["error_kind"] == ("timeout" if failure == "probe" else "invalid_request")
    assert audio.read_bytes() == original
    assert not list(tmp_path.glob("token-plan-asr-*"))


@pytest.mark.parametrize("failure,kind", [(TimeoutError, "timeout"), (ConnectionError, "network"),
                                         (KeyboardInterrupt, None)])
def test_transport_interruption_closes_without_retry(asr, audio, monkeypatch, failure, kind):
    calls = []
    class Connection:
        def __init__(self, *a, **kw): pass
        def request(self, *a, **kw): calls.append("request")
        def getresponse(self): raise failure("private-path-or-key")
        def close(self): calls.append("close")
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    if kind is None:
        with pytest.raises(KeyboardInterrupt):
            asr.TokenPlanASR().transcribe(audio)
    else:
        result = asr.TokenPlanASR().transcribe(audio)
        assert result["error_kind"] == kind
        assert "completion unknown" in result["error"]
        assert "private" not in result["error"]
    assert calls == ["request", "close"]
    assert audio.exists()


@pytest.mark.parametrize("status,kind", [(401, "credential"), (403, "entitlement"), (429, "quota"), (503, "upstream")])
def test_status_errors_do_not_read_private_bodies(asr, audio, monkeypatch, status, kind):
    class Connection:
        def __init__(self, *a, **kw): pass
        def request(self, *a, **kw): pass
        def getresponse(self):
            return types.SimpleNamespace(status=status, read=lambda limit: pytest.fail("Do not read error bodies"))
        def close(self): pass
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    result = asr.TokenPlanASR().transcribe(audio)
    assert result["error_kind"] == kind
    assert not result["success"]


@pytest.mark.parametrize("raw", [b'[]', b'null', b'{"error":{"message":"private"}}', b'{', b'\xff'])
def test_response_error_categories(asr, audio, monkeypatch, raw):
    class Connection:
        def __init__(self, *a, **kw): pass
        def request(self, *a, **kw): pass
        def getresponse(self): return types.SimpleNamespace(status=200, read=io.BytesIO(raw).read)
        def close(self): pass
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    result = asr.TokenPlanASR().transcribe(audio)
    assert result["error_kind"] in {"response", "upstream"}
    assert not result["success"] and "private" not in result["error"]


def test_core_file_safety_precedes_open(asr, audio, monkeypatch):
    monkeypatch.setattr(asr, "get_read_block_error", lambda path: "Access denied: private-path")
    monkeypatch.setattr(asr.os, "open", lambda *a: pytest.fail("Protected file must not be opened"))
    result = asr.TokenPlanASR().transcribe(audio)
    assert result["error_kind"] == "invalid_request"
    assert "Core file safety" in result["error"] and "private" not in result["error"]


def test_changed_input_snapshot_is_rejected(asr, audio, monkeypatch):
    original_stat = asr.os.fstat
    count = 0
    def fstat(fd):
        nonlocal count
        info = original_stat(fd)
        count += 1
        if count == 1:
            return info
        return types.SimpleNamespace(st_size=info.st_size + 1, st_mtime_ns=info.st_mtime_ns)
    monkeypatch.setattr(asr.os, "fstat", fstat)
    monkeypatch.setattr(asr, "post", lambda *a: pytest.fail("Changed recording must not upload"))
    result = asr.TokenPlanASR().transcribe(audio)
    assert not result["success"] and "changed while reading" in result["error"]


@pytest.mark.parametrize("eof", [False, True])
def test_trickled_or_late_eof_response_times_out_once(asr, monkeypatch, eof):
    clock, calls, closed = [0.0], [], []
    monkeypatch.setattr(asr.time, "monotonic", lambda: clock[0])
    class Response:
        status = 200
        def read(self, cap): pytest.fail("Buffered read must not hide trickled bytes")
        def read1(self, cap):
            clock[0] += 31
            return b"" if eof else b" "
    class Connection:
        def __init__(self, *args, **kw): pass
        def request(self, *args, **kw): calls.append(args[0])
        def getresponse(self):
            if eof: clock[0] = 31
            return Response()
        def close(self): closed.append(True)
    monkeypatch.setattr(asr.http.client, "HTTPSConnection", Connection)
    with pytest.raises(asr.ASRError) as caught:
        asr.post({}, "synthetic")
    assert caught.value.kind == "timeout"
    assert calls == ["POST"] and closed
