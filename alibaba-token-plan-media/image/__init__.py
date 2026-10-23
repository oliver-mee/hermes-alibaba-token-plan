"""Native Token Plan ImageGenProvider. See LICENSE and docs/native-image.md.

Adapted from rriggs/hermes-plugin-dashscope-image at
f13665c97eb852b3ef90e30e020dbdcf0c9dc38b (MIT, Colorado Rob).
No automatic model switching, PAYG routing, discovery, or paid POST retries.
"""
from __future__ import annotations

import base64
import http.client
import json
from pathlib import Path
import re
import time

from agent.image_gen_provider import (
    DEFAULT_ASPECT_RATIO, ImageGenProvider, error_response, resolve_aspect_ratio,
    success_response,
)
from agent.secret_scope import get_secret

from .media import cache_image, source_image

CATALOGUE = json.loads(Path(__file__).with_name("catalogue.json").read_text())
# Catalogue eligibility and a supported wire contract are separate gates. A
# future catalogue refresh must never route an unknown family through Qwen.
CONTRACTS = {
    "qwen-image-2.0": {"async": False, "sources": 3, "min_pixels": 512**2, "max_pixels": 2048**2},
    "qwen-image-2.0-pro": {"async": False, "sources": 3, "min_pixels": 512**2, "max_pixels": 2048**2},
    "qwen-image-3.0-pro": {"async": False, "sources": 3, "min_pixels": 512**2, "max_pixels": 2048**2, "aspect_ratio": (1/8, 8)},
    "wan2.7-image": {"async": True, "sources": 9, "min_pixels": 768**2, "max_pixels": 2048**2},
    "wan2.7-image-pro": {"async": True, "sources": 9, "min_pixels": 768**2, "max_pixels": 4096**2},
}
# Hosts and namespaces are deliberately not configurable. Personal aliases retain
# the chat provider's legacy-first precedence, within the same region and tier.
PROFILES = {
    "alibaba-token-plan": ("global", "personal", "token-plan.maas.qwencloudapi.com", (
        "QWEN_TOKEN_PLAN_API_KEY", "BAILIAN_TOKEN_PLAN_API_KEY", "ALIBABA_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY")),
    "alibaba-token-plan-team": ("global", "team", "token-plan.maas.qwencloudapi.com", (
        "ALIBABA_TOKEN_PLAN_TEAM_API_KEY",)),
    "alibaba-token-plan-cn": ("cn", "personal", "token-plan.maas.qianwenaiapi.com", (
        "ALIBABA_TOKEN_PLAN_CN_API_KEY", "ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY")),
    "alibaba-token-plan-cn-team": ("cn", "team", "token-plan.maas.qianwenaiapi.com", (
        "ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY",)),
}
SYNC_PATH = "/api/v1/services/aigc/multimodal-generation/generation"
ASYNC_PATH = "/api/v1/services/aigc/image-generation/generation"
MAX_RESPONSE = 1024 * 1024
MAX_REQUEST = 32 * 1024 * 1024
JOB_SECONDS = 300
MAX_POLLS = 60
SIZES = {"landscape": "1280*720", "square": "1024*1024", "portrait": "720*1280"}
OPTIONS = {"size", "seed", "negative_prompt", "watermark", "prompt_extend", "thinking_mode", "n"}
TOKEN_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")


class ImageError(Exception):
    def __init__(self, message, kind="provider_error"):
        super().__init__(message)
        self.kind = kind


def _config():
    from hermes_cli.config import load_config
    try:
        cfg = load_config()
    except Exception:
        raise ImageError("Could not read image provider configuration", "configuration_error") from None
    section = cfg.get("image_gen", {})
    if not isinstance(section, dict):
        raise ValueError("image_gen must be a mapping")
    return section


def _request(host, key, method, path, payload=None, *, asynchronous=False, timeout=120):
    """Fixed-origin, bounded JSON. No redirects or implicit request retries."""
    body = json.dumps(payload).encode() if payload is not None else None
    if body is not None and len(body) > MAX_REQUEST:
        raise ImageError("Image request exceeds the plugin's 32 MiB safety cap", "invalid_input")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if asynchronous:
        headers["X-DashScope-Async"] = "enable"
    conn = http.client.HTTPSConnection(host, timeout=timeout)
    deadline = time.monotonic() + timeout
    try:
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        chunks = []
        count = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ImageError("Gateway response exceeded its time limit", "timeout")
            if getattr(conn, "sock", None) is not None:
                conn.sock.settimeout(remaining)
            chunk = getattr(response, "read1", response.read)(min(65536, MAX_RESPONSE + 1 - count))
            if time.monotonic() >= deadline:
                raise ImageError("Gateway response exceeded its time limit", "timeout")
            if not chunk:
                break
            chunks.append(chunk)
            count += len(chunk)
            if count > MAX_RESPONSE:
                break
        raw = b"".join(chunks)
        if len(raw) > MAX_RESPONSE:
            raise ImageError("Gateway response exceeds 1 MiB", "invalid_response")
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ImageError("Gateway returned invalid JSON", "invalid_response") from None
        if not isinstance(data, dict):
            raise ImageError("Gateway returned a non-object response", "invalid_response")
        if not 200 <= response.status < 300 or data.get("code"):
            # Never echo server messages, signed URLs, response bodies or exceptions:
            # these can contain keys, prompts, private paths or account identifiers.
            kind = {401: "authentication_error", 402: "quota_error", 403: "entitlement_error",
                    429: "quota_error"}.get(response.status, "api_error")
            code = data.get("code")
            known = {"InvalidApiKey": "authentication_error", "AccessDenied": "entitlement_error",
                     "QuotaExhausted": "quota_error", "Throttling": "quota_error"}
            kind = known.get(code, kind) if isinstance(code, str) else kind
            raise ImageError(f"Token Plan image request rejected (HTTP {response.status}); check region, tier, entitlement and quota", kind)
        return data
    finally:
        conn.close()


def _parameters(model, aspect, edit, options):
    contract = CONTRACTS[model]
    wan = contract["async"]
    params = {"n": 1, "size": options.get("size", SIZES[aspect])}
    if wan:
        params["enable_sequential"] = False
    for key, value in options.items():
        if key == "size":
            continue
        if key == "n":
            if type(value) is not int or value != 1:
                raise ValueError("This plugin generates exactly one image per request (n=1)")
        elif key in ("watermark", "prompt_extend", "thinking_mode"):
            if type(value) is not bool:
                raise ValueError(f"{key} must be a boolean")
            if key == "prompt_extend" and wan:
                raise ValueError("prompt_extend is only supported for Qwen Image")
            if key == "thinking_mode" and (not wan or edit):
                raise ValueError("thinking_mode is only supported for Wan text-to-image")
        elif key == "seed":
            if type(value) is not int or not 0 <= value <= 2147483647:
                raise ValueError("seed must be an integer in [0, 2147483647]")
        elif key == "negative_prompt":
            if not isinstance(value, str) or len(value) > 500:
                raise ValueError("negative_prompt must be a string of at most 500 characters")
        params[key] = value
    size = params["size"]
    if not isinstance(size, str):
        raise ValueError("size must be a width*height string")
    if not re.fullmatch(r"[1-9][0-9]{0,4}\*[1-9][0-9]{0,4}", size):
        raise ValueError("size must use explicit width*height pixels; shorthand sizes are not supported")
    width, height = map(int, size.split("*"))
    low = contract["min_pixels"]
    high = min(contract["max_pixels"], 2048**2) if edit else contract["max_pixels"]
    ratio_low, ratio_high = contract.get("aspect_ratio", (1/8, 8) if wan else (0, float("inf")))
    if not low <= width * height <= high or not ratio_low <= width/height <= ratio_high:
        raise ValueError("size is outside the documented pixel range for this model/mode")
    return params


def _image_url(data):
    try:
        choices = data["output"]["choices"]
        urls = [item["image"] for choice in choices
                for item in choice["message"]["content"] if "image" in item]
        if len(urls) == 1 and isinstance(urls[0], str):
            return urls[0]
    except (KeyError, TypeError):
        pass
    raise ImageError("Gateway response did not contain exactly one image", "invalid_response")


class TokenPlanImageProvider(ImageGenProvider):
    def __init__(self, name):
        self._name = name
        self.region, self.tier, self.host, self.keys = PROFILES[name]

    @property
    def name(self):
        return self._name

    @property
    def display_name(self):
        return f"Token Plan Image ({self.region.upper()} {self.tier.title()})"

    def _key(self):
        return next((value.strip() for name in self.keys
                     if (value := get_secret(name)) and value.strip()), "")

    def is_available(self):
        try:
            return bool(self._key())
        except Exception:
            return False

    def list_models(self):
        return [{"id": row["id"], "display": row["id"], "speed": "Unmeasured",
                 "strengths": "Generation and editing; Token Plan inference unverified",
                 "price": "Token Plan entitlement listed; credit cost unmeasured",
                 "inference_verified": False, "catalogue_status": row["status"]}
                for row in CATALOGUE if row["id"] in CONTRACTS
                and self.tier in row["tiers"] and self.region in row["regions"]]

    def default_model(self):
        return self.list_models()[0]["id"]

    def get_setup_schema(self):
        return {"name": self.display_name, "badge": "token-plan",
                "tag": "Opt-in image backend; inference and credit cost unverified",
                "env_vars": [{"key": self.keys[-1], "prompt": f"{self.display_name} API key",
                              "url": "https://www.qianwenai.com/" if self.region == "cn" else "https://www.qwencloud.com/"}]}

    def _selection(self, explicit=None):
        cfg = _config()
        scoped = cfg.get(self.name, {})
        if not isinstance(scoped, dict):
            raise ValueError("Provider image configuration must be a mapping")
        model = explicit or scoped.get("model") or cfg.get("model") or self.default_model()
        if model not in [row["id"] for row in self.list_models()]:
            raise ValueError("Selected exact image model is unknown or ineligible for this region/tier")
        options = scoped.get("options", {})
        if not isinstance(options, dict) or set(options) - OPTIONS:
            raise ValueError("Unknown image options; see docs/native-image.md")
        return model, options

    def capabilities(self):
        try:
            model, _ = self._selection()
        except Exception:
            return {"modalities": ["text"], "max_reference_images": 0}
        count = CONTRACTS[model]["sources"]
        return {"modalities": ["text", "image"], "max_source_images": count,
                "max_reference_images": count - 1, "supports_upscale": False}

    def generate(self, prompt, aspect_ratio=DEFAULT_ASPECT_RATIO, *, image_url=None,
                 reference_image_urls=None, **kwargs):
        aspect = resolve_aspect_ratio(aspect_ratio)
        model, task_id = "", None
        submitted = False
        try:
            if not isinstance(prompt, str) or not prompt.strip():
                raise ValueError("A non-empty prompt is required")
            # Operational byte cap, not a claim about the model's token window.
            if len(prompt.encode()) > 16384:
                raise ValueError("Prompt exceeds the plugin's 16 KiB safety cap")
            model, options = self._selection(kwargs.get("model"))
            options = {**options, **{k: v for k, v in kwargs.items() if k in OPTIONS}}
            if kwargs.get("upscale"):
                raise ValueError("This backend does not support upscaling")
            refs = reference_image_urls or []
            if not isinstance(refs, (list, tuple)):
                raise ValueError("reference_image_urls must be a list")
            sources = ([image_url] if image_url is not None else []) + list(refs)
            max_sources = CONTRACTS[model]["sources"]
            if len(sources) > max_sources:
                raise ValueError(f"Selected model supports at most {max_sources} total source images")
            params = _parameters(model, aspect, bool(sources), options)
            key = self._key()
            if not key:
                raise ImageError(f"Set {self.keys[-1]} for the selected region/tier", "missing_credentials")
            content = []
            total = 0
            for source in sources:
                try:
                    raw, mime = source_image(source)
                except Exception:
                    raise ImageError("Source image could not be read safely; check type, size, path and URL", "invalid_input") from None
                total += len(raw)
                if total > 20 * 1024 * 1024:
                    raise ValueError("Source images exceed the plugin's 20 MiB combined safety cap")
                content.append({"image": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"})
            content.append({"text": prompt.strip()})
            payload = {"model": model, "input": {"messages": [{"role": "user", "content": content}]},
                       "parameters": params}
            asynchronous = CONTRACTS[model]["async"]
            from tools.interrupt import is_interrupted
            if is_interrupted():
                raise ImageError("Image generation interrupted before submission", "interrupted")
            # No other model or endpoint is tried after a rejection/ambiguous POST.
            submitted = True
            data = _request(self.host, key, "POST", ASYNC_PATH if asynchronous else SYNC_PATH,
                            payload, asynchronous=asynchronous)
            if asynchronous:
                output = data.get("output", {})
                task_id = output.get("task_id") if isinstance(output, dict) else None
                if not isinstance(task_id, str) or not TOKEN_ID.fullmatch(task_id) or key in task_id:
                    task_id = None
                    raise ImageError("Submission returned no valid task ID; outcome may be unknown", "invalid_response")
                deadline = time.monotonic() + JOB_SECONDS
                for attempt in range(MAX_POLLS):
                    if is_interrupted():
                        raise ImageError("Image wait interrupted; remote task may continue", "interrupted")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ImageError("Image job exceeded the plugin's five-minute wait", "timeout")
                    data = _request(self.host, key, "GET", f"/api/v1/tasks/{task_id}", timeout=min(30, remaining))
                    if is_interrupted():
                        raise ImageError("Image wait interrupted; remote task may continue", "interrupted")
                    if time.monotonic() >= deadline:
                        raise ImageError("Image job exceeded the plugin's five-minute wait", "timeout")
                    output = data.get("output", {})
                    if not isinstance(output, dict):
                        raise ImageError("Invalid task response", "invalid_response")
                    state = output.get("task_status")
                    if state == "SUCCEEDED":
                        break
                    if state not in ("PENDING", "RUNNING"):
                        kind = "job_failed" if state in ("FAILED", "CANCELED", "CANCELLED", "UNKNOWN", "EXPIRED") else "invalid_response"
                        raise ImageError("Image job failed, was cancelled, expired, or returned an unknown status", kind)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ImageError("Image job exceeded the plugin's five-minute wait", "timeout")
                    time.sleep(min(2 + attempt, 10, remaining))
                else:
                    raise ImageError("Image job reached the plugin's polling limit", "timeout")
            if is_interrupted():
                raise ImageError("Image generation interrupted; request may have completed", "interrupted")
            image_url = _image_url(data)
            try:
                path = cache_image(image_url, self.name)
            except Exception:
                raise ImageError("Generated image could not be safely cached; no remote URL returned", "artifact_error") from None
            return success_response(image=str(path), model=model, prompt=prompt, aspect_ratio=aspect,
                                    provider=self.name, modality="image" if sources else "text",
                                    extra={"size": params["size"], "task_id": task_id})
        except (ValueError, ImageError) as exc:
            kind = exc.kind if isinstance(exc, ImageError) else "invalid_input"
            result = error_response(error=str(exc), error_type=kind, provider=self.name,
                                    model=model, prompt=prompt if isinstance(prompt, str) else "", aspect_ratio=aspect)
        except Exception:
            result = error_response(error="Image operation failed; network, response or artifact unavailable",
                                    error_type="operation_error", provider=self.name,
                                    model=model, aspect_ratio=aspect)
        result.update(task_id=task_id, submission_attempted=submitted, retry_safe=not submitted)
        if submitted:
            result["note"] = "Do not resubmit automatically; the request may have been billed."
        return result


def register(ctx):
    for name in PROFILES:
        ctx.register_image_gen_provider(TokenPlanImageProvider(name))
