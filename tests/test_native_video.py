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
        interrupt = types.ModuleType("tools.interrupt")
        interrupt.is_interrupted = lambda: False
        monkeypatch.setitem(sys.modules, "tools.interrupt", interrupt)
    spec = importlib.util.spec_from_file_location("_native_video", ROOT / "video-gen/alibaba-token-plan-video/__init__.py", submodule_search_locations=[str(ROOT / "video-gen/alibaba-token-plan-video")])
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, mod)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "_config", lambda: {})
    monkeypatch.setattr(mod, "is_interrupted", lambda: False)
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
    assert result["error_type"] == ("cancelled" if state in ("CANCELED", "CANCELLED") else "job_failed")
    assert result["task_id"] == "task-123"
    assert "synthetic-secret" not in json.dumps(result)
    assert sum(c[0] == "POST" for c in wire[0]) == 1


def test_pending_running_success(video, wire):
    wire[1][1:1] = [{"output": {"task_status": state}} for state in ["PENDING", "RUNNING"]]
    assert video.TokenPlanVideoProvider().generate("A cloud")["success"]
    assert [c[0] for c in wire[0]] == ["POST", "GET", "GET", "GET"]


def test_poll_timeout(video, wire, monkeypatch):
    clock = iter([0, 601])
    monkeypatch.setattr(video.time, "monotonic", lambda: next(clock))
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
    assert caught.value.retryable == (status in (429, 500))
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
    assert provider.capabilities()["resolutions"] == ["480p", "720p"]
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


@pytest.mark.parametrize("when", ["before", "submitted", "polled"])
def test_native_stop_never_resubmits_or_downloads(video, wire, monkeypatch, when):
    stopped = lambda: when == "before" or len(wire[0]) >= (1 if when == "submitted" else 2)
    monkeypatch.setattr(video, "is_interrupted", stopped)
    monkeypatch.setattr(video, "save_url_video", lambda *a, **kw: pytest.fail("Stopped task downloaded"))
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "cancelled"
    assert len(wire[0]) == {"before": 0, "submitted": 1, "polled": 2}[when]
    if when != "before":
        assert result["task_id"] == "task-123"
        assert result["resubmit_safe"] is False


def test_stop_during_backoff(video, wire, monkeypatch):
    wire[1][1] = {"output": {"task_status": "RUNNING"}}
    stopped = []
    monkeypatch.setattr(video, "is_interrupted", lambda: bool(stopped))
    monkeypatch.setattr(video.time, "sleep", lambda seconds: stopped.append(seconds))
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "cancelled"
    assert stopped == [0.25]
    assert len(wire[0]) == 2


def test_poll_retry_budget_exhausted(video, wire):
    import httpx
    wire[1][1:] = [httpx.ReadTimeout("synthetic-secret")] * 3
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "poll_failed"
    assert result["task_id"] == "task-123"
    assert result["resubmit_safe"] is False
    assert [c[0] for c in wire[0]] == ["POST", "GET", "GET", "GET"]
    assert "synthetic-secret" not in json.dumps(result)


@pytest.mark.parametrize("value", [0, -1, 601, True, "30", float("nan"), float("inf")])
def test_invalid_poll_timeout_before_credentials(video, wire, monkeypatch, value):
    monkeypatch.setattr(video, "_config", lambda: {"poll_timeout": value})
    monkeypatch.setattr(video, "get_secret_str", lambda *a: pytest.fail("Invalid settings read secrets"))
    assert video.TokenPlanVideoProvider().generate("A cloud")["error_type"] == "invalid_request"
    assert not wire[0]


def test_short_poll_timeout_keeps_task_for_recovery(video, wire, monkeypatch):
    monkeypatch.setattr(video, "_config", lambda: {"poll_timeout": 1})
    clock = iter([10, 12])
    monkeypatch.setattr(video.time, "monotonic", lambda: next(clock))
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "timeout"
    assert result["task_id"] == "task-123"
    assert len(wire[0]) == 1


def test_picker_metadata_is_complete_and_independent(video):
    provider = video.TokenPlanVideoProvider()
    rows = provider.list_models()
    assert all(row["min_duration"] == row["max_duration"] == 5 for row in rows)
    assert all("live validation pending" in row["strengths"] for row in rows)
    assert rows[-1]["resolutions"] == ["480p", "720p"]
    rows[0]["modalities"].append("video")
    rows[-1]["resolutions"].append("1080p")
    assert provider.list_models()[0]["modalities"] == ["text"]
    assert provider.list_models()[-1]["resolutions"] == ["480p", "720p"]


def test_generated_catalogue_is_current():
    target = ROOT / "video-gen/alibaba-token-plan-video/catalogue.py"
    before = target.read_bytes()
    runpy.run_path(str(ROOT / "scripts/sync-video-catalogue.py"))
    assert target.read_bytes() == before


@pytest.mark.parametrize("model,resolution,refs", [
    ("happyhorse-1.1-t2v", ["720p"], 0),
    ("happyhorse-1.1-i2v", ["720p"], 0),
    ("happyhorse-1.1-r2v", ["720p"], 9),
    ("wan3.0-video", ["480p", "720p"], 0),
])
def test_native_dynamic_schema(video, monkeypatch, model, resolution, refs):
    if os.environ.get("HERMES_NATIVE_TEST") != "1":
        pytest.skip("Real Hermes schema runs in dedicated integration subprocess")
    from tools import video_generation_tool as tool
    from hermes_cli import config
    monkeypatch.setattr(config, "load_config", lambda: {"video_gen": {"model": model}})
    monkeypatch.setattr(tool, "_read_configured_video_model", lambda: model)
    monkeypatch.setattr(tool, "_resolve_active_provider", lambda: video.TokenPlanVideoProvider())
    schema = tool._build_dynamic_video_schema()
    props = schema["parameters"]["properties"]
    assert props["resolution"]["enum"] == resolution
    assert props["duration"]["minimum"] == props["duration"]["maximum"] == 5
    assert props.get("reference_image_urls", {}).get("maxItems", 0) == refs
    assert not {"audio", "seed", "upscale", "negative_prompt", "model"}.intersection(props)


def test_real_hermes_interrupt_signal(video, wire, monkeypatch):
    if os.environ.get("HERMES_NATIVE_TEST") != "1":
        pytest.skip("Real Hermes interrupt runs in dedicated integration subprocess")
    from tools.interrupt import is_interrupted, set_interrupt
    monkeypatch.setattr(video, "is_interrupted", is_interrupted)
    set_interrupt(True)
    try:
        assert video.TokenPlanVideoProvider().generate("A cloud")["error_type"] == "cancelled"
        assert not wire[0]
        assert is_interrupted(), "Provider must not clear the host's stop signal"
    finally:
        set_interrupt(False)


@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503, 504])
def test_http_poll_recovers_and_closes_client(video, monkeypatch, status):
    import httpx
    real_client = httpx.Client
    calls, clients = [], []
    def transport(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"output": {"task_id": "task-123"}})
        if len(calls) == 2:
            return httpx.Response(status, text="synthetic-secret")
        return httpx.Response(200, json={"output": {"task_status": "SUCCEEDED", "video_url": "https://example.com/a.mp4"}})
    def client(**kw):
        instance = real_client(transport=httpx.MockTransport(transport), **kw)
        clients.append(instance)
        return instance
    monkeypatch.setattr(httpx, "Client", client)
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["success"] == (status not in (401, 403))
    assert [r.method for r in calls] == (["POST", "GET"] if status in (401, 403) else ["POST", "GET", "GET"])
    assert len({r.headers["Authorization"] for r in calls}) == 1
    assert clients[0].is_closed


@pytest.mark.parametrize("resolution", [None, "480p"])
def test_native_wan_prompt_only_dispatch(video, wire, monkeypatch, resolution):
    if os.environ.get("HERMES_NATIVE_TEST") != "1":
        pytest.skip("Real Hermes dispatch runs in dedicated integration subprocess")
    from tools import video_generation_tool as tool
    provider = video.TokenPlanVideoProvider()
    monkeypatch.setattr(tool, "_resolve_active_provider", lambda: provider)
    monkeypatch.setattr(tool, "_read_configured_video_model", lambda: "wan3.0-video")
    args = {"prompt": "A cloud"}
    if resolution:
        args["resolution"] = resolution
    result = json.loads(tool._handle_video_generate(args))
    assert result["success"]
    assert wire[0][0][2]["json"]["parameters"]["resolution"] == (resolution or "720p").upper()


@pytest.mark.parametrize("stop", [False, True])
def test_stream_deadline_and_stop_close_response(video, monkeypatch, stop):
    import httpx
    clock = [0.0]
    stopped, closed = [], []
    monkeypatch.setattr(video.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(video, "is_interrupted", lambda: bool(stopped))
    class SlowStream(httpx.SyncByteStream):
        def __iter__(self):
            for chunk in (b'{', b'"output":', b'{}}'):
                clock[0] += 0.4
                if stop and clock[0] > 0.5:
                    stopped.append(True)
                yield chunk
        def close(self):
            closed.append(True)
    def reply(request):
        assert request.extensions["timeout"]["read"] <= 1.0
        return httpx.Response(200, stream=SlowStream())
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        with pytest.raises(video.RequestFailure) as caught:
            video._json_request(client, "GET", "https://example.com/api", deadline=1.0)
    assert caught.value.kind == ("cancelled" if stop else "timeout")
    assert closed


def test_late_success_keeps_task_without_downloading(video, wire, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(video.time, "monotonic", lambda: clock[0])
    request = video._json_request
    def late(*args, **kwargs):
        result = request(*args, **kwargs)
        if args[1] == "GET":
            clock[0] = 601
        return result
    monkeypatch.setattr(video, "_json_request", late)
    monkeypatch.setattr(video, "save_url_video", lambda *a, **kw: pytest.fail("Late task downloaded"))
    result = video.TokenPlanVideoProvider().generate("A cloud")
    assert result["error_type"] == "timeout"
    assert result["task_id"] == "task-123"
    assert result["resubmit_safe"] is False
    assert [c[0] for c in wire[0]] == ["POST", "GET"]
