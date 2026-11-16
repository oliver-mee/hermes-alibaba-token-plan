"""Offline image protocol, security and configuration contracts.

Also run with real Hermes through the isolated integration subprocess.
"""
import base64
import importlib.util
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "alibaba-token-plan-media/image"
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6d8sAAAAASUVORK5CYII=")
URL = "https://example.com/image.png"


@pytest.fixture
def image(monkeypatch, tmp_path):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline test attempted to open a socket")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    if os.environ.get("HERMES_NATIVE_TEST") != "1":
        agent = types.ModuleType("agent")
        agent.__path__ = []
        abc = types.ModuleType("agent.image_gen_provider")
        abc.ImageGenProvider = type("ImageGenProvider", (), {})
        abc.DEFAULT_ASPECT_RATIO = "landscape"
        abc.resolve_aspect_ratio = lambda x: x if x in ("landscape", "square", "portrait") else "landscape"
        abc.error_response = lambda **kw: dict(success=False, image=None, **kw)
        abc.success_response = lambda **kw: dict(success=True, **{k: v for k, v in kw.items() if k != "extra"}, **kw.get("extra", {}))
        secret = types.ModuleType("agent.secret_scope")
        secret.get_secret = lambda name: ""
        safety = types.ModuleType("agent.file_safety")
        safety.raise_if_read_blocked = lambda path: None
        constants = types.ModuleType("hermes_constants")
        constants.get_hermes_home = lambda: tmp_path / "hermes"
        interrupt = types.ModuleType("tools.interrupt")
        interrupt.is_interrupted = lambda: False
        for name, mod in (("agent", agent), ("agent.image_gen_provider", abc),
                          ("agent.secret_scope", secret), ("agent.file_safety", safety),
                          ("hermes_constants", constants), ("tools.interrupt", interrupt)):
            monkeypatch.setitem(sys.modules, name, mod)
    spec = importlib.util.spec_from_file_location("_native_image", PLUGIN / "__init__.py",
                                                submodule_search_locations=[str(PLUGIN)])
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_config", lambda: {})
    monkeypatch.setattr(module, "get_secret", lambda name: "synthetic-token-plan-key")
    monkeypatch.setattr(module, "cache_image", lambda *args: tmp_path / "cached.png")
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    return module


@pytest.fixture
def wire(image, monkeypatch):
    calls, replies = [], []
    def request(host, key, method, path, payload=None, **options):
        calls.append((host, key, method, path, payload, options))
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(image, "_request", request)
    return calls, replies


def success():
    return {"output": {"task_status": "SUCCEEDED", "choices": [
        {"message": {"content": [{"image": URL}]}}]}}


def provider(image, name="alibaba-token-plan"):
    return image.TokenPlanImageProvider(name)




@pytest.mark.parametrize("name", list(("alibaba-token-plan", "alibaba-token-plan-team",
                                     "alibaba-token-plan-cn", "alibaba-token-plan-cn-team")))
def test_image3_explicit_selection_preserves_defaults(image, wire, name):
    calls, replies = wire
    replies.extend([success(), success()])
    p = provider(image, name)
    assert p.default_model() == ("wan2.7-image" if p.tier == "personal" else "qwen-image-2.0")
    for kwargs in ({}, {"image_url": "data:image/png;base64," + base64.b64encode(PNG).decode()}):
        result = p.generate("cloud", model="qwen-image-3.0-pro", **kwargs)
        assert result["success"] and result["model"] == "qwen-image-3.0-pro"
    assert len(calls) == 2
    assert all(c[3] == image.SYNC_PATH and c[4]["model"] == "qwen-image-3.0-pro" for c in calls)




@pytest.mark.parametrize("size", ["4*65536", "65536*4"])
def test_image3_rejects_extreme_ratio_before_submission(image, wire, size):
    result = provider(image).generate("cloud", model="qwen-image-3.0-pro", size=size)
    assert not result["success"]
    assert not wire[0]
    assert not result.get("submission_attempted", False)


def test_registration_catalogue_and_evidence(image):
    registered = []
    image.register(types.SimpleNamespace(register_image_gen_provider=registered.append))
    assert [p.name for p in registered] == list(image.PROFILES)
    source = runpy.run_path(str(ROOT / "alibaba-token-plan/fallback_models.py"))["MEDIA_MODELS"]
    assert [r["id"] for r in image.CATALOGUE] == [r[0] for r in source if r[1] == "image"]
    for p in registered:
        rows = p.list_models()
        assert len(rows) == (3 if p.tier == "personal" else 5)
        assert not any(r["inference_verified"] for r in rows)
        assert p.get_setup_schema()["env_vars"][0]["key"] == p.keys[-1]
        assert all("unverified" in r["endpoint"] for r in image.CATALOGUE)


@pytest.mark.parametrize("name", ["alibaba-token-plan", "alibaba-token-plan-team",
                                 "alibaba-token-plan-cn", "alibaba-token-plan-cn-team"])
def test_region_tier_and_secret_isolation(image, wire, monkeypatch, name):
    calls, replies = wire
    replies.extend([{"output": {"task_id": "job-1"}}, success()])
    lookups = []
    monkeypatch.setattr(image, "get_secret", lambda key: lookups.append(key) or ("synthetic" if key == image.PROFILES[name][3][-1] else ""))
    result = provider(image, name).generate("A cloud", model="wan2.7-image")
    assert result["success"]
    assert lookups == list(image.PROFILES[name][3])
    assert all(c[0] == image.PROFILES[name][2] for c in calls)
    assert calls[0][3] == image.ASYNC_PATH and calls[0][5]["asynchronous"]
    assert calls[1][3] == "/api/v1/tasks/job-1"
    assert calls[0][4]["parameters"] == {"n": 1, "size": "1280*720", "enable_sequential": False}


def test_legacy_precedence_and_no_payg(image, wire, monkeypatch):
    monkeypatch.setattr(image, "get_secret", lambda name: "old" if name == "QWEN_TOKEN_PLAN_API_KEY" else "new")
    assert provider(image)._key() == "old"
    monkeypatch.setattr(image, "get_secret", lambda name: "payg" if name == "DASHSCOPE_API_KEY" else "")
    assert not provider(image).is_available()
    assert provider(image).generate("cloud")["error_type"] == "missing_credentials"
    assert not wire[0]


def test_qwen_sync_config_precedence_and_options(image, wire, monkeypatch):
    calls, replies = wire
    replies.append(success())
    monkeypatch.setattr(image, "_config", lambda: {
        "model": "qwen-image-2.0", "alibaba-token-plan-team": {
            "model": "qwen-image-2.0-pro", "options": {"prompt_extend": False, "watermark": True, "seed": 42}}})
    p = provider(image, "alibaba-token-plan-team")
    assert p._selection()[0] == "qwen-image-2.0-pro"
    result = p.generate("A cloud", "portrait", model="qwen-image-2.0")
    assert result["success"] and result["model"] == "qwen-image-2.0"
    assert len(calls) == 1 and calls[0][3] == image.SYNC_PATH
    assert calls[0][4]["parameters"] == {"n": 1, "size": "720*1280", "prompt_extend": False, "watermark": True, "seed": 42}


@pytest.mark.parametrize("model,total", [("qwen-image-2.0", 3), ("qwen-image-2.0-pro", 3),
                                         ("wan2.7-image", 9), ("wan2.7-image-pro", 9)])
def test_edit_reference_order_and_no_model_switch(image, wire, tmp_path, model, total):
    calls, replies = wire
    if model.startswith("wan"):
        replies.append({"output": {"task_id": "job-1"}})
    replies.append(success())
    source = tmp_path / "source.png"
    source.write_bytes(PNG)
    p = provider(image, "alibaba-token-plan-team")
    result = p.generate("Make blue", model=model, image_url=str(source),
                        reference_image_urls=[f"data:image/png;base64,{base64.b64encode(PNG).decode()}"] * (total - 1))
    assert result["success"] and result["modality"] == "image" and result["model"] == model
    content = calls[0][4]["input"]["messages"][0]["content"]
    assert len(content) == total + 1 and content[-1] == {"text": "Make blue"}
    assert all(c["image"].startswith("data:image/png;base64,") for c in content[:-1])
    assert p.generate("edit", model=model, reference_image_urls=[str(source)] * (total + 1))["error_type"] == "invalid_input"


@pytest.mark.parametrize("args", [dict(model="unknown"), dict(model="qwen-image-2.0"),
    dict(n=2), dict(n=True), dict(seed=True), dict(seed=-1), dict(seed=2147483648),
    dict(watermark="false"), dict(size="4K"), dict(size="1*1"), dict(size="4096*4096"),
    dict(size="1024*90000"), dict(prompt_extend=True), dict(upscale=True),
    dict(reference_image_urls="bad"), dict(negative_prompt="x" * 501)])
def test_invalid_inputs_do_not_submit(image, wire, args):
    result = provider(image).generate("A cloud", **args)
    assert result["error_type"] == "invalid_input" and not wire[0]


def test_per_model_pixel_limits_and_modes(image, wire):
    assert image._parameters("qwen-image-2.0", "square", False, {"size": "512*512"})["size"] == "512*512"
    assert image._parameters("wan2.7-image-pro", "square", False, {"size": "4096*4096"})["size"] == "4096*4096"
    for model, edit, opts in [("wan2.7-image-pro", True, {"size": "4096*4096"}),
                              ("qwen-image-2.0", False, {"thinking_mode": True}),
                              ("wan2.7-image", True, {"thinking_mode": True})]:
        with pytest.raises(ValueError):
            image._parameters(model, "square", edit, opts)


def test_missing_and_unscoped_secrets(image, wire, monkeypatch):
    def unscoped(name):
        raise RuntimeError("private synthetic key detail")
    monkeypatch.setattr(image, "get_secret", unscoped)
    assert not provider(image).is_available()
    result = provider(image).generate("A cloud")
    assert not result["success"] and "private" not in result["error"] and not wire[0]


@pytest.mark.parametrize("state", ["FAILED", "CANCELED", "CANCELLED", "UNKNOWN", "EXPIRED", "surprise"])
def test_terminal_job_errors_no_resubmit(image, wire, state):
    calls, replies = wire
    replies.extend([{"output": {"task_id": "job-1"}}, {"output": {"task_status": state, "message": "secret"}}])
    result = provider(image).generate("A cloud")
    assert not result["success"] and result["task_id"] == "job-1"
    assert not result["retry_safe"] and "secret" not in result["error"]
    assert len([c for c in calls if c[2] == "POST"]) == 1


def test_poll_pending_running_success(image, wire):
    calls, replies = wire
    replies.extend([{"output": {"task_id": "job-1"}}, {"output": {"task_status": "PENDING"}},
                    {"output": {"task_status": "RUNNING"}}, success()])
    assert provider(image).generate("cloud")["success"] and len(calls) == 4


def test_poll_bound_and_interruption(image, wire, monkeypatch):
    calls, replies = wire
    monkeypatch.setattr(image, "MAX_POLLS", 2)
    replies.extend([{"output": {"task_id": "job-1"}}] + [{"output": {"task_status": "RUNNING"}}] * 2)
    result = provider(image).generate("cloud")
    assert result["error_type"] == "timeout" and result["task_id"] == "job-1" and len(calls) == 3
    checks = iter([False, True])
    monkeypatch.setattr(sys.modules["tools.interrupt"], "is_interrupted", lambda: next(checks))
    replies.append({"output": {"task_id": "job-2"}})
    result = provider(image).generate("cloud")
    assert result["error_type"] == "interrupted" and result["task_id"] == "job-2"
    before = len(calls)
    monkeypatch.setattr(sys.modules["tools.interrupt"], "is_interrupted", lambda: True)
    result = provider(image).generate("cloud")
    assert result["error_type"] == "interrupted" and result["task_id"] is None
    assert len(calls) == before and result["retry_safe"]


@pytest.mark.parametrize("reply", [TimeoutError("key=secret"), {"output": {}},
                                  {"output": {"task_id": "../../private"}}])
def test_ambiguous_submit_no_retry(image, wire, reply):
    calls, replies = wire
    replies.append(reply)
    result = provider(image).generate("cloud")
    assert not result["success"] and result["submission_attempted"] and not result["retry_safe"]
    assert len(calls) == 1 and "secret" not in result["error"]


def test_poll_and_download_failure_keep_task_id(image, wire, monkeypatch):
    calls, replies = wire
    replies.extend([{"output": {"task_id": "job-1"}}, OSError("private URL")])
    assert provider(image).generate("cloud")["task_id"] == "job-1"
    replies.extend([{"output": {"task_id": "job-2"}}, success()])
    def failed(*args):
        raise OSError("private signed URL")
    monkeypatch.setattr(image, "cache_image", failed)
    result = provider(image).generate("cloud")
    assert result["task_id"] == "job-2" and result["image"] is None
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("status,kind", [(401, "authentication_error"), (402, "quota_error"),
    (403, "entitlement_error"), (429, "quota_error"), (500, "api_error"), (302, "api_error")])
def test_http_errors_sanitised(image, monkeypatch, status, kind):
    calls = []
    class Connection:
        def __init__(self, host, timeout):
            calls.append((host, timeout))
        def request(self, *args, **kwargs):
            calls.append((args, kwargs))
        def getresponse(self):
            import io
            return types.SimpleNamespace(status=status, read=io.BytesIO(b'{"message":"secret-key private-path"}').read)
        def close(self):
            calls.append("closed")
    monkeypatch.setattr(image.http.client, "HTTPSConnection", Connection)
    result = provider(image).generate("cloud")
    assert result["error_type"] == kind and "secret-key" not in result["error"]
    assert calls[-1] == "closed" and len(calls) == 3


def test_response_and_request_bounds(image, monkeypatch):
    class Connection:
        def __init__(self, *args, **kwargs): pass
        def request(self, *args, **kwargs): pass
        def getresponse(self):
            return types.SimpleNamespace(status=200, read=lambda cap: b"x" * cap)
        def close(self): pass
    monkeypatch.setattr(image.http.client, "HTTPSConnection", Connection)
    assert provider(image).generate("cloud")["error_type"] == "invalid_response"
    monkeypatch.setattr(image, "MAX_REQUEST", 1)
    assert provider(image).generate("cloud")["error_type"] == "invalid_input"


def test_source_file_safety(image, tmp_path, monkeypatch):
    media = sys.modules["_native_image.media"]
    valid = tmp_path / "a.png"
    valid.write_bytes(PNG)
    assert media.source_image(str(valid)) == (PNG, "image/png")
    link = tmp_path / "link.png"
    link.symlink_to(valid)
    fifo = tmp_path / "fifo.png"
    os.mkfifo(fifo)
    empty = tmp_path / "empty.png"
    empty.touch()
    wrong = tmp_path / "wrong.png"
    wrong.write_text("not an image")
    for source in (str(link), str(fifo), str(empty), str(wrong), str(tmp_path),
                   "relative.png", "http://example.com/x.png", "data:image/png;base64,@@@"):
        with pytest.raises((ValueError, OSError)):
            media.source_image(source)
    monkeypatch.setattr(media, "MAX_SOURCE", 1)
    with pytest.raises(ValueError): media.source_image(str(valid))


def test_remote_and_cache_bounds(image, monkeypatch, tmp_path):
    media = sys.modules["_native_image.media"]
    safety = types.ModuleType("tools.url_safety")
    status, headers, chunks = [200], {"content-type": "image/png"}, [PNG]
    class Response:
        @property
        def status_code(self): return status[0]
        def __enter__(self): return self
        def __exit__(self, *args): pass
        @property
        def headers(self): return headers
        def iter_bytes(self, **kwargs): return iter(chunks)
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, method, url):
            assert method == "GET"
            return Response()
    def safe_client(**kwargs):
        assert 0 < kwargs.pop("timeout") <= 30
        assert kwargs == {"follow_redirects": False, "trust_env": False}
        return Client()
    safety.create_ssrf_safe_client = safe_client
    monkeypatch.setitem(sys.modules, "tools.url_safety", safety)
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(0, 0, 0, "", ("93.184.216.34", 443))])
    assert media._download(URL, 1024) == (PNG, "image/png")
    path = media.cache_image(URL, "synthetic")
    assert path.read_bytes() == PNG and path.stat().st_mode & 0o777 == 0o600
    assert "cache/generated/images" in str(path)
    for state in (302, 403):
        status[0] = state
        with pytest.raises(ValueError): media._download(URL, 1024)
    status[0] = 200
    for bad in ("text/html", "image/gif", "application/octet-stream"):
        headers["content-type"] = bad
        with pytest.raises(ValueError): media._download(URL, 1024)
    headers["content-type"] = "image/png"
    headers["content-length"] = "1025"
    with pytest.raises(ValueError): media._download(URL, 1024)
    headers.pop("content-length")
    with pytest.raises(ValueError): media._download(URL, 1)
    chunks[:] = [b"<html>not an image</html>"]
    with pytest.raises(ValueError): media._download(URL, 1024)
    for address in ("127.0.0.1", "169.254.169.254", "10.0.0.1", "::1"):
        monkeypatch.setattr(socket, "getaddrinfo", lambda *a, _ip=address, **kw: [(0, 0, 0, "", (_ip, 443))])
        with pytest.raises(ValueError): media._https_url(URL)
    for url in ("http://example.com/x", "https://user:pass@example.com/x", "file:///tmp/x", "https://example.com:8443/x"):
        with pytest.raises(ValueError): media._https_url(url)


def test_unlisted_evidence_retained_by_export(image):
    script = runpy.run_path(str(ROOT / "scripts/sync-image-catalogue.py"))
    row = dict(id="synthetic-unlisted-image", kind="image", status="unlisted", tiers=["team"],
               regions=["global"], endpoint="documented route; historical inference")
    assert json.loads(script["render"]({"models": [row]}))[0]["status"] == "unlisted"


def test_unknown_future_catalogue_cannot_acquire_a_wire_contract(image, monkeypatch):
    monkeypatch.setattr(image, "CATALOGUE", [*image.CATALOGUE,
        dict(id="unknown-image", tiers=["team"], regions=["global"], status="unlisted")])
    p = provider(image, "alibaba-token-plan-team")
    assert "unknown-image" not in [m["id"] for m in p.list_models()]
    assert p.generate("cloud", model="unknown-image")["error_type"] == "invalid_input"


def test_supported_unlisted_row_is_not_hidden(image, monkeypatch):
    rows = [dict(row, status="unlisted") for row in image.CATALOGUE]
    monkeypatch.setattr(image, "CATALOGUE", rows)
    assert all(row["catalogue_status"] == "unlisted" for row in provider(image).list_models())


def test_guard_errors_do_not_expose_private_paths(image, wire, monkeypatch):
    def guarded(source):
        raise ValueError("private-path synthetic-secret")
    monkeypatch.setattr(image, "source_image", guarded)
    result = provider(image).generate("edit", image_url="/synthetic/source.png")
    assert result["error_type"] == "invalid_input" and not wire[0]
    assert "private-path" not in json.dumps(result) and "synthetic-secret" not in json.dumps(result)


def test_cache_symlink_is_rejected_before_network(image, monkeypatch, tmp_path):
    media = sys.modules["_native_image.media"]
    import hermes_constants
    home, outside = tmp_path / "profile", tmp_path / "outside"
    home.mkdir()
    outside.mkdir()
    (home / "cache").symlink_to(outside)
    monkeypatch.setattr(hermes_constants, "get_hermes_home", lambda: home)
    with pytest.raises(ValueError, match="symlinked"):
        media.cache_image(URL, "synthetic")
    assert not list(outside.iterdir())


@pytest.mark.parametrize("failure", ["trickle", "late_eof", "interrupt"])
def test_download_observes_deadline_and_interrupt(image, monkeypatch, failure):
    media = sys.modules["_native_image.media"]
    clock, stopped, closed = [0.0], [], []
    monkeypatch.setattr(media.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(media, "_https_url", lambda url: None)
    monkeypatch.setattr(sys.modules["tools.interrupt"], "is_interrupted", lambda: bool(stopped))
    class Response:
        status_code, headers = 200, {"content-type": "image/png"}
        def __enter__(self): return self
        def __exit__(self, *args): closed.append(True)
        def iter_bytes(self, chunk_size=None):
            if failure == "late_eof":
                yield PNG
                clock[0] = 61
                return
            if chunk_size is not None:
                pytest.fail("Buffered iteration hides cancellation and trickled bytes")
            clock[0] = 61 if failure == "trickle" else 1
            if failure == "interrupt": stopped.append(True)
            yield PNG
    class Client:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def stream(self, *args): return Response()
    safety = types.ModuleType("tools.url_safety")
    safety.create_ssrf_safe_client = lambda **kw: Client()
    monkeypatch.setitem(sys.modules, "tools.url_safety", safety)
    with pytest.raises(ValueError, match="interrupted|time limit"):
        media._download(URL, 1024)
    assert closed


@pytest.mark.parametrize("stop", [False, True])
def test_late_poll_success_never_downloads(image, wire, monkeypatch, stop):
    clock, stopped = [0.0], []
    monkeypatch.setattr(image.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(sys.modules["tools.interrupt"], "is_interrupted", lambda: bool(stopped))
    calls, replies = wire
    replies.extend([{"output": {"task_id": "job-1"}}, success()])
    request = image._request
    def late(*args, **kw):
        data = request(*args, **kw)
        if args[2] == "GET":
            clock[0] = 301
            if stop: stopped.append(True)
        return data
    monkeypatch.setattr(image, "_request", late)
    monkeypatch.setattr(image, "cache_image", lambda *a: pytest.fail("Late image downloaded"))
    result = provider(image).generate("cloud")
    assert result["error_type"] == ("interrupted" if stop else "timeout")
    assert result["task_id"] == "job-1" and not result["retry_safe"]
    assert [c[2] for c in calls] == ["POST", "GET"]


def test_changing_source_is_rejected(image, monkeypatch, tmp_path):
    media = sys.modules["_native_image.media"]
    source = tmp_path / "source.png"
    source.write_bytes(PNG)
    fstat, count = media.os.fstat, [0]
    def changed(fd):
        info = fstat(fd)
        count[0] += 1
        if count[0] == 2:
            return types.SimpleNamespace(st_size=info.st_size + 1, st_mtime_ns=info.st_mtime_ns)
        return info
    monkeypatch.setattr(media.os, "fstat", changed)
    with pytest.raises(ValueError, match="changed while reading"):
        media.source_image(str(source))


@pytest.mark.parametrize("eof", [False, True])
def test_json_read_crossing_deadline_is_not_accepted(image, monkeypatch, eof):
    clock, calls, closed = [0.0], [], []
    monkeypatch.setattr(image.time, "monotonic", lambda: clock[0])
    class Response:
        status = 200
        def read(self, cap):
            clock[0] = 121
            return b"" if eof else json.dumps(success()).encode()
    class Connection:
        def __init__(self, *a, **kw): pass
        def request(self, *a, **kw): calls.append(a[0])
        def getresponse(self): return Response()
        def close(self): closed.append(True)
    monkeypatch.setattr(image.http.client, "HTTPSConnection", Connection)
    result = provider(image, "alibaba-token-plan-team").generate("cloud", model="qwen-image-2.0")
    assert result["error_type"] == "timeout" and not result["retry_safe"]
    assert calls == ["POST"] and closed
