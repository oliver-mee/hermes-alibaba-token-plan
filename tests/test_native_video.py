"""Offline video wire tests; also run against real Hermes with HERMES_NATIVE_TEST=1."""
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def video(monkeypatch):
    import socket
    def blocked(*args, **kwargs):
        raise AssertionError("Offline test attempted a socket connection")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    if os.environ.get("HERMES_NATIVE_TEST") != "1":
        abc = types.ModuleType("agent.video_gen_provider")
        abc.VideoGenProvider = type("VideoGenProvider", (), {})
        abc.error_response = lambda **kw: dict(success=False, video=None, **kw)
        abc.success_response = lambda **kw: dict(success=True, **kw)
        abc.save_url_video = lambda *a, **kw: Path("/synthetic/video.mp4")
        agent = types.ModuleType("agent")
        agent.__path__ = []
        secrets = types.ModuleType("agent.secret_scope")
        secrets.get_secret_str = lambda name: ""
        monkeypatch.setitem(sys.modules, "agent", agent)
        monkeypatch.setitem(sys.modules, "agent.video_gen_provider", abc)
        monkeypatch.setitem(sys.modules, "agent.secret_scope", secrets)
    spec = importlib.util.spec_from_file_location("_native_video", ROOT / "video-gen/alibaba-token-plan-video/__init__.py", submodule_search_locations=[str(ROOT / "video-gen/alibaba-token-plan-video")])
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_config", lambda: {})
    if os.environ.get("HERMES_NATIVE_TEST") == "1":
        from hermes_cli import config
        monkeypatch.setattr(config, "load_config", lambda: {})
    else:
        config = types.ModuleType("hermes_cli.config")
        config.load_config = lambda: {}
        monkeypatch.setitem(sys.modules, "hermes_cli.config", config)
    monkeypatch.setattr(mod, "get_secret_str", lambda name: "synthetic-secret")
    monkeypatch.setattr(mod, "save_url_video", lambda *a, **kw: Path("/synthetic/video.mp4"))
    monkeypatch.setattr(mod.time, "sleep", lambda seconds: None)
    return mod


@pytest.fixture
def wire(video, monkeypatch):
    calls = []
    replies = [{"output": {"task_id": "task-123"}}, {"output": {"task_status": "SUCCEEDED", "video_url": "https://example.com/video.mp4"}}]
    def request(client, method, url, **kwargs):
        calls.append((method, url, kwargs))
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(video, "_json_request", request)
    return calls, replies


def test_catalogue_generated_order(video):
    source = runpy.run_path(str(ROOT / "alibaba-token-plan/fallback_models.py"))["MEDIA_MODELS"]
    assert [r["id"] for r in video.VIDEO_MODELS] == [r[0] for r in source if r[1] == "video"]


@pytest.mark.parametrize("profile", ["global-personal", "global-team", "cn-personal", "cn-team"])
def test_region_and_key_isolation(video, wire, monkeypatch, profile):
    monkeypatch.setattr(video, "_config", lambda: {"profile": profile})
    lookups = []
    monkeypatch.setattr(video, "get_secret_str", lambda name: lookups.append(name) or "synthetic-secret")
    assert video.TokenPlanVideoProvider().generate("A cloud")["success"]
    base, key = video.PROFILES[profile]
    assert lookups == [key]
    assert all(call[1].startswith(base + "/api/v1/") for call in wire[0])
    assert wire[0][0][2]["headers"]["X-DashScope-Async"] == "enable"


@pytest.mark.parametrize("model,inputs,expected", [
    ("happyhorse-1.1-t2v", {}, {}),
    ("happyhorse-1.1-i2v", {"image_url": "synthetic-image"}, {"media": [{"type": "first_frame", "url": "synthetic-image"}]}),
    ("happyhorse-1.1-r2v", {"reference_image_urls": ["image1", "image2"]}, {"media": [{"type": "reference_image", "url": "image1"}, {"type": "reference_image", "url": "image2"}]}),
    ("wan3.0-video", {"resolution": "480p"}, {}),
])
def test_exact_wire_shapes(video, wire, monkeypatch, model, inputs, expected):
    monkeypatch.setattr(video, "_source", lambda value: value)
    result = video.TokenPlanVideoProvider().generate("A cloud", model=model, **inputs)
    assert result["success"]
    payload = wire[0][0][2]["json"]
    assert payload["model"] == model
    assert payload["input"] == dict(prompt="A cloud", **expected)
    assert "size" not in payload["parameters"]
    assert payload["parameters"]["resolution"] == ("480P" if model.startswith("wan") else "720P")
    if model.endswith("-i2v"):
        assert "ratio" not in payload["parameters"]
    else:
        assert payload["parameters"]["ratio"] == ("adaptive" if model.startswith("wan") else "16:9")


@pytest.mark.parametrize("kwargs", [
    {"model": "wan3.0-video-t2v"}, {"duration": 30}, {"duration": True},
    {"aspect_ratio": "9:16"}, {"resolution": "1080p"}, {"audio": True},
    {"audio": False}, {"seed": 1}, {"negative_prompt": "bad"}, {"upscale": True},
    {"model": "happyhorse-1.1-i2v"}, {"model": "happyhorse-1.1-r2v"},
    {"image_url": "/etc/passwd"}, {"reference_image_urls": ["x"] * 10},
    {"model": "wan3.0-video", "resolution": "480p", "image_url": "https://example.com/a.png"},
])
def test_invalid_before_payment(video, wire, kwargs):
    assert video.TokenPlanVideoProvider().generate("A cloud", **kwargs)["error_type"] == "invalid_request"
    assert wire[0] == []


def test_missing_key_no_fallback(video, wire, monkeypatch):
    monkeypatch.setattr(video, "get_secret_str", lambda name: "")
    assert not video.TokenPlanVideoProvider().is_available()
    assert video.TokenPlanVideoProvider().generate("A cloud")["error_type"] == "missing_credentials"
    assert not wire[0]


def test_unknown_profile(video, wire, monkeypatch):
    monkeypatch.setattr(video, "_config", lambda: {"profile": "payg"})
    assert not video.TokenPlanVideoProvider().is_available()
    assert not video.TokenPlanVideoProvider().generate("A cloud")["success"]
    assert not wire[0]


@pytest.mark.parametrize("reply", [TimeoutError("synthetic-secret"), {}, {"output": {"task_id": "../bad"}}])
def test_ambiguous_submission_never_retried(video, wire, reply):
    wire[1][:] = [reply]
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "submission_unknown"
    assert result["resubmit_safe"] is False
    assert "synthetic-secret" not in json.dumps(result)
    assert len(wire[0]) == 1


@pytest.mark.parametrize("state", ["FAILED", "CANCELED", "CANCELLED", "EXPIRED", "UNKNOWN", None])
def test_terminal_failures(video, wire, state):
    wire[1][1] = {"output": {"task_status": state, "message": "synthetic-secret"}}
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "job_failed"
    assert result["task_id"] == "task-123"
    assert "synthetic-secret" not in json.dumps(result)
    assert sum(c[0] == "POST" for c in wire[0]) == 1


def test_pending_running_success(video, wire):
    wire[1][1:1] = [{"output": {"task_status": state}} for state in ["PENDING", "RUNNING"]]
    assert video.TokenPlanVideoProvider().generate("A cloud")["success"]
    assert [c[0] for c in wire[0]] == ["POST", "GET", "GET", "GET"]


def test_poll_timeout(video, wire, monkeypatch):
    monkeypatch.setattr(video, "POLL_DEADLINE", 0)
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "timeout"
    assert result["task_id"] == "task-123"
    assert len(wire[0]) == 1


def test_poll_network_error(video, wire):
    wire[1][1] = TimeoutError("synthetic-secret")
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "poll_failed"
    assert result["task_id"] == "task-123"
    assert "synthetic-secret" not in json.dumps(result)


def test_cache_safety_and_failure(video, wire, monkeypatch):
    def download(url, **kwargs):
        assert kwargs["max_bytes"] == 200 * 1024 * 1024
        assert kwargs["timeout"] == 120
        assert kwargs["require_video_content_type"] is True
        assert "headers" not in kwargs
        raise ValueError("private-url")
    monkeypatch.setattr(video, "save_url_video", download)
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "download_failed"
    assert result["video"] is None
    assert result["task_id"] == "task-123"
    assert "private-url" not in json.dumps(result)


@pytest.mark.parametrize("status,kind", [(401, "credentials_or_entitlement"), (403, "credentials_or_entitlement"), (429, "quota"), (500, "api_error"), (302, "api_error")])
def test_http_errors_redacted(video, status, kind):
    import httpx
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(status, text="synthetic-secret")))
    with client, pytest.raises(video.RequestFailure) as caught:
        video._json_request(client, "POST", "https://example.com/api")
    assert caught.value.kind == kind
    assert "synthetic-secret" not in str(caught.value)


def test_response_bound(video):
    import httpx
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * (1024 * 1024 + 1)))) as client:
        with pytest.raises(video.RequestFailure):
            video._json_request(client, "GET", "https://example.com/api")


def test_data_image_and_local_rejection(video, monkeypatch):
    safety = types.ModuleType("tools.url_safety")
    from urllib.parse import urlsplit
    safety.is_safe_url = lambda value: urlsplit(value).hostname == "example.com"
    monkeypatch.setitem(sys.modules, "tools.url_safety", safety)
    assert video._source("data:image/png;base64,YQ==").startswith("data:")
    assert video._source("https://example.com/image.png").startswith("https:")
    for value in ["/etc/passwd", "http://example.com/a.png", "https://127.0.0.1/a.png", "data:text/plain;base64,YQ==", "https://user:password@example.com/a"]:
        with pytest.raises(ValueError):
            video._source(value)


def test_native_registration_and_tool_dispatch(video, wire, monkeypatch):
    if os.environ.get("HERMES_NATIVE_TEST") != "1":
        pytest.skip("Real Hermes contract runs in dedicated integration subprocess")
    from hermes_cli.plugins import PluginContext, PluginManager, PluginManifest
    from agent import video_gen_registry
    ctx = PluginContext(PluginManifest(name="alibaba-token-plan-video"), PluginManager())
    video.register(ctx)
    provider = video_gen_registry.get_provider("alibaba-token-plan")
    assert isinstance(provider, video.TokenPlanVideoProvider)
    from tools import video_generation_tool as tool
    monkeypatch.setattr(tool, "_resolve_active_provider", lambda: provider)
    monkeypatch.setattr(tool, "_read_configured_video_provider", lambda: provider.name)
    monkeypatch.setattr(tool, "_read_configured_video_model", lambda: "happyhorse-1.1-t2v")
    result = json.loads(tool._handle_video_generate({"prompt": "A cloud", "model": "ignored-agent-model"}))
    assert result["success"]
    assert result["model"] == "happyhorse-1.1-t2v"


def test_model_precedence_and_capabilities(video, monkeypatch):
    config = sys.modules["hermes_cli.config"]
    monkeypatch.setattr(config, "load_config", lambda: {"video_gen": {"model": "wan3.0-video"}})
    monkeypatch.setattr(video, "_config", lambda: {"model": "happyhorse-1.1-i2v"})
    provider = video.TokenPlanVideoProvider()
    assert provider.default_model() == "wan3.0-video"
    assert provider.capabilities()["resolutions"] == ["480p"]
    assert provider.capabilities()["max_reference_images"] == 0
    monkeypatch.setattr(config, "load_config", lambda: {})
    assert provider.default_model() == "happyhorse-1.1-i2v"
    assert provider.capabilities()["modalities"] == ["image"]
    assert provider.get_setup_schema()["env_vars"][0]["key"] == "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY"


def test_registration_version_error(video):
    with pytest.raises(RuntimeError, match="v0.22.0"):
        video.register(object())


def test_real_http_transport_submits_once(video, monkeypatch):
    import httpx
    calls = []
    real_client = httpx.Client
    def transport(request):
        calls.append(request.method)
        if request.method == "POST":
            raise httpx.ReadTimeout("synthetic-secret")
        raise AssertionError("No poll allowed after ambiguous submission")
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(transport), **kw))
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert calls == ["POST"]
    assert result["error_type"] == "submission_unknown"
    assert not result["resubmit_safe"]
    assert "synthetic-secret" not in json.dumps(result)


@pytest.mark.parametrize("output", [{}, {"video_url": "http://example.com/video.mp4"}, {"video_url": "file:///tmp/video.mp4"}])
def test_missing_or_unsafe_download(video, wire, output):
    wire[1][1] = {"output": dict(task_status="SUCCEEDED", **output)}
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "download_failed"
    assert result["task_id"] == "task-123"


def test_api_error_body_redacted(video):
    import httpx
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"code": "AccessDenied", "message": "synthetic-secret"}))) as client:
        with pytest.raises(video.RequestFailure) as caught:
            video._json_request(client, "POST", "https://example.com/api")
    assert "synthetic-secret" not in str(caught.value)
