"""Native Token Plan video; adapted from rriggs/hermes-plugin-dashscope-video.

MIT, Copyright (c) 2026 Colorado Rob; see LICENSE and docs/native-video.md.
Only the dated, documented request subset is enabled. Never retry submission.
"""
from __future__ import annotations

import base64
import re
import time
from urllib.parse import urlsplit

from agent.secret_scope import get_secret_str
from agent.video_gen_provider import (
    VideoGenProvider, error_response, success_response, save_url_video,
)

# Copied from the generated chat catalogue by scripts/sync-video-catalogue.py.
from .catalogue import VIDEO_MODELS

PROFILES = {
    "global-personal": ("https://token-plan.maas.qwencloudapi.com", "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY"),
    "global-team": ("https://token-plan.maas.qwencloudapi.com", "ALIBABA_TOKEN_PLAN_TEAM_API_KEY"),
    "cn-personal": ("https://token-plan.maas.qianwenaiapi.com", "ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY"),
    "cn-team": ("https://token-plan.maas.qianwenaiapi.com", "ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY"),
}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 200 * 1024 * 1024
POLL_DEADLINE = 600.0


def _config():
    from hermes_cli.config import load_config
    section = load_config().get("video_gen", {})
    return section.get("alibaba-token-plan", {})


def _source(value):
    """Only public HTTPS or bounded image data URIs; local reads belong to Hermes."""
    from tools.url_safety import is_safe_url
    if not isinstance(value, str) or len(value) > MAX_IMAGE_BYTES * 4 // 3 + 128:
        raise ValueError("Invalid or oversized image source")
    if value.startswith("data:"):
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", value)
        if not match:
            raise ValueError("Use a PNG, JPEG or WebP base64 image")
        try:
            raw = base64.b64decode(match[2], validate=True)
        except ValueError:
            raise ValueError("Invalid image encoding") from None
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("Image must be nonempty and at most 10 MiB")
        return value
    parts = urlsplit(value)
    if (len(value) > 8192 or parts.scheme != "https" or parts.username or parts.password
            or not is_safe_url(value)):
        raise ValueError("Use a public HTTPS image URL or bounded image data URI; local files are not read")
    return value


def _json_request(client, method, url, **kwargs):
    # Streaming bounds even error/JSON responses. No redirects carrying credentials.
    with client.stream(method, url, **kwargs) as response:
        if response.status_code != 200:
            code = response.status_code
            kind = "credentials_or_entitlement" if code in (401, 403) else "quota" if code == 429 else "api_error"
            raise RequestFailure(kind, f"Video endpoint returned HTTP {code}")
        data = bytearray()
        for chunk in response.iter_bytes(chunk_size=64 * 1024):
            data.extend(chunk)
            if len(data) > 1024 * 1024:
                raise RequestFailure("invalid_response", "Video endpoint response exceeded 1 MiB")
    import json
    parsed = json.loads(data)
    if not isinstance(parsed, dict):
        raise ValueError("Expected response object")
    if parsed.get("code"):
        # Never echo upstream messages, URLs, request bodies or headers.
        raise RequestFailure("api_error", "Video endpoint reported an API error; check entitlement and quota")
    return parsed


class RequestFailure(Exception):
    def __init__(self, kind, message):
        self.kind = kind
        super().__init__(message)


class TokenPlanVideoProvider(VideoGenProvider):
    @property
    def name(self):
        return "alibaba-token-plan"

    @property
    def display_name(self):
        return "Alibaba Token Plan Video (experimental)"

    def _settings(self):
        cfg = _config()
        profile = cfg.get("profile", "global-personal")
        if profile not in PROFILES:
            raise ValueError("Select global-personal, global-team, cn-personal or cn-team")
        base, env = PROFILES[profile]
        # Native media intentionally uses canonical keys only: no PAYG or cross-tier fallback.
        return cfg, base, env

    def is_available(self):
        try:
            _, _, env = self._settings()
            return bool(get_secret_str(env).strip())
        except (ValueError, TypeError, AttributeError):
            return False

    def list_models(self):
        return [dict(row) for row in VIDEO_MODELS]

    def default_model(self):
        from hermes_cli.config import load_config
        configured = load_config().get("video_gen", {}).get("model")
        return configured or _config().get("model") or "happyhorse-1.1-t2v"

    def capabilities(self):
        model = self.default_model()
        refs = model == "happyhorse-1.1-r2v"
        return {
            "modalities": ["image"] if model in ("happyhorse-1.1-i2v", "happyhorse-1.1-r2v") else ["text"],
            "aspect_ratios": ["16:9"], "resolutions": ["480p"] if model == "wan3.0-video" else ["720p"],
            "min_duration": 5, "max_duration": 5,
            "supports_audio": False, "supports_seed": False,
            "supports_negative_prompt": False, "supports_upscale": False,
            "max_reference_images": 9 if refs else 0,
        }

    def get_setup_schema(self):
        _, _, env = self._settings()
        return {"name": self.display_name, "badge": "paid", "tag": "Select region/tier explicitly; live validation pending",
                "env_vars": [{"key": env, "prompt": "Token Plan key for the selected profile",
                              "url": "https://www.qwencloud.com/"}]}

    def generate(self, prompt, *, model=None, image_url=None, reference_image_urls=None,
                 duration=None, aspect_ratio="16:9", resolution="720p", negative_prompt=None,
                 audio=None, seed=None, **kwargs):
        task_id = None
        try:
            model_id = model or self.default_model()
        except (ValueError, TypeError, AttributeError):
            model_id = ""

        def fail(message, kind):
            result = error_response(error=message, error_type=kind, provider=self.name,
                                    model=model_id, prompt=prompt, aspect_ratio=aspect_ratio)
            if task_id:
                result["task_id"] = task_id
                result["resubmit_safe"] = False
            return result

        try:
            cfg, base, env = self._settings()
            if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000:
                raise ValueError("Prompt must contain 1–4000 characters")
            if model_id not in {row["id"] for row in VIDEO_MODELS}:
                raise ValueError("Unknown video model; select an exact catalogue ID")
            if duration is not None and (type(duration) is not int or duration != 5):
                raise ValueError("Only the documented five-second request subset is enabled")
            if aspect_ratio != "16:9":
                raise ValueError("Only 16:9 is enabled in this initial subset")
            if negative_prompt is not None or audio is not None or seed is not None or kwargs.get("upscale"):
                raise ValueError("Negative prompt, audio control, seed and upscale are not enabled")
            refs = reference_image_urls or []
            if not isinstance(refs, list) or len(refs) > 9 or (image_url and refs):
                raise ValueError("Use one first frame or up to nine references, never both")
            is_wan = model_id == "wan3.0-video"
            wanted_resolution = "480p" if is_wan else "720p"
            if resolution.lower() != wanted_resolution:
                raise ValueError(f"Select {wanted_resolution} for this documented model subset")
            inputs = {"prompt": prompt.strip()}
            params = {"duration": 5, "resolution": wanted_resolution.upper()}
            if is_wan:
                if image_url or refs:
                    raise ValueError("Wan image/reference modes are gated pending verified wire contracts")
                params["ratio"] = "adaptive"
            elif model_id.endswith("-i2v"):
                if not image_url or refs:
                    raise ValueError("HappyHorse i2v requires image_url")
                inputs["media"] = [{"type": "first_frame", "url": _source(image_url)}]
            elif model_id.endswith("-r2v"):
                if image_url or not refs:
                    raise ValueError("HappyHorse r2v requires reference_image_urls")
                inputs["media"] = [{"type": "reference_image", "url": _source(ref)} for ref in refs]
                params["ratio"] = aspect_ratio
            else:
                if image_url or refs:
                    raise ValueError("Select happyhorse-1.1-i2v or happyhorse-1.1-r2v for image inputs")
                params["ratio"] = aspect_ratio
            key = get_secret_str(env).strip()
            if not key:
                return fail(f"Set {env} for the selected region/tier; no fallback is used", "missing_credentials")
        except ValueError as exc:
            return fail(str(exc), "invalid_request")
        except (TypeError, AttributeError):
            return fail("Invalid video configuration or parameter type; see docs/native-video.md", "invalid_request")

        import httpx
        # httpx defaults to zero transport retries. Never retry a paid POST, even on timeout.
        with httpx.Client(timeout=30, follow_redirects=False) as client:
            headers = {"Authorization": f"Bearer {key}", "X-DashScope-Async": "enable"}
            try:
                submitted = _json_request(client, "POST", base + "/api/v1/services/aigc/video-generation/video-synthesis",
                                          headers=headers, json={"model": model_id, "input": inputs, "parameters": params})
                task_id = submitted.get("output", {}).get("task_id")
                if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
                    task_id = None
                    raise ValueError("Missing task ID")
            except RequestFailure as exc:
                result = fail(str(exc) + "; inspect the task console before resubmitting", exc.kind)
                result["resubmit_safe"] = False
                return result
            except Exception:
                result = fail("Submission outcome unknown. Do not resubmit; inspect the provider task console first.", "submission_unknown")
                result["resubmit_safe"] = False
                return result

            deadline = time.monotonic() + POLL_DEADLINE
            interval = 2.0
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return fail("Polling deadline reached; task may still be running. Do not resubmit.", "timeout")
                    polled = _json_request(client, "GET", base + "/api/v1/tasks/" + task_id,
                                           headers={"Authorization": f"Bearer {key}"}, timeout=min(30, remaining))
                    output = polled.get("output", {})
                    status = output.get("task_status")
                    if status == "SUCCEEDED":
                        break
                    if status not in ("PENDING", "RUNNING"):
                        return fail("Video task ended without success; inspect task status in the console", "job_failed")
                    time.sleep(min(interval, max(0, deadline - time.monotonic())))
                    interval = min(interval * 1.5, 10)
            except RequestFailure as exc:
                return fail(str(exc), exc.kind)
            except Exception:
                return fail("Polling failed; task may still be running. Do not resubmit.", "poll_failed")
        try:
            url = output.get("video_url")
            if not isinstance(url, str) or urlsplit(url).scheme != "https":
                raise ValueError("Missing HTTPS video URL")
            saved = save_url_video(url, prefix="token_plan", timeout=120,
                                   max_bytes=MAX_VIDEO_BYTES, require_video_content_type=True)
        except Exception:
            return fail("Task succeeded but safe caching failed. Recover the output from the task console; do not resubmit.", "download_failed")
        return success_response(video=str(saved), model=model_id, prompt=prompt,
                                modality="image" if image_url or refs else "text", aspect_ratio="" if is_wan or image_url else aspect_ratio,
                                duration=5, provider=self.name, extra={"task_id": task_id})


def register(ctx):
    # Older Hermes retains the independent chat plugin; no monkey-patching or defaults.
    if not callable(getattr(ctx, "register_video_gen_provider", None)):
        raise RuntimeError("Native video requires Hermes v0.22.0 or newer; chat remains independent")
    ctx.register_video_gen_provider(TokenPlanVideoProvider())
