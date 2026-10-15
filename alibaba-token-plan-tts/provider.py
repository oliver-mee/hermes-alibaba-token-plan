"""DashScope run-task synthesis, one isolated connection per invocation.

Native integration pattern: Deepgram voice plugin (MIT, Jayson Santos dos Reis)
2d31b885 and Fish Audio Hermes (Apache-2.0, Electric Sheep) 4c987455.
No third-party implementation code is copied; see docs/native-tts.md.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import uuid

from agent.tts_provider import TTSProvider

MAX_TEXT = 2000
MAX_AUDIO = 16 * 1024 * 1024
TIMEOUT = 60
VOICE = "longanlingxin"
HOSTS = {"global": "token-plan.maas.qwencloudapi.com", "cn": "token-plan.maas.qianwenaiapi.com"}


def _models():
    # Use the installed generated catalogue, not a second maintained model list.
    path = Path(__file__).resolve().parent.parent / "model-providers" / "alibaba-token-plan" / "fallback_models.py"
    if not path.is_file():  # source checkout
        path = Path(__file__).resolve().parent.parent / "alibaba-token-plan" / "fallback_models.py"
    spec = importlib.util.spec_from_file_location("_token_plan_tts_catalogue", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.MEDIA_MODELS


class TokenPlanTTSProvider(TTSProvider):
    streams_pcm = False
    stream_sample_rate = None

    def __init__(self, region="global", tier="personal"):
        if region not in HOSTS or tier not in ("personal", "team"):
            raise ValueError("Unsupported Token Plan region or tier")
        self.region, self.tier = region, tier

    @property
    def name(self):
        return "alibaba-token-plan" + ("-cn" if self.region == "cn" else "") + ("-team" if self.tier == "team" else "")

    @property
    def display_name(self):
        return f"Token Plan TTS ({self.region}, {self.tier})"

    @property
    def voice_compatible(self):
        return True  # Hermes performs the ffmpeg Opus delivery conversion.

    @property
    def key_names(self):
        canonical = "ALIBABA_TOKEN_PLAN_" + ("CN_" if self.region == "cn" else "") + self.tier.upper() + "_API_KEY"
        aliases = ()
        if self.tier == "personal":
            aliases = ("ALIBABA_TOKEN_PLAN_CN_API_KEY",) if self.region == "cn" else (
                "QWEN_TOKEN_PLAN_API_KEY", "BAILIAN_TOKEN_PLAN_API_KEY", "ALIBABA_TOKEN_PLAN_API_KEY")
        return (*aliases, canonical)

    def _key(self):
        from tools.tool_backend_helpers import resolve_provider_secret
        # Empty pool id prevents a generic credential pool from overriding tier isolation.
        return next((key for name in self.key_names if (key := resolve_provider_secret(name, ""))), "")

    def is_available(self):
        try:
            from websockets.sync.client import connect  # noqa: F401
            return bool(self._key())
        except Exception:
            return False

    def list_models(self):
        return [{"id": row[0], "display": row[0], "max_text_length": MAX_TEXT}
                for row in _models() if row[1] == "tts" and self.tier in row[2] and self.region in row[3]]

    def list_voices(self):
        return [{"id": VOICE, "display": "Longan Lingxin (verified 2026-09-08)"}]

    def get_setup_schema(self):
        return {"name": self.display_name, "badge": "subscription", "tag": "Whole-file MP3; region/tier entitlement must be checked",
                "env_vars": [{"key": self.key_names[-1], "prompt": f"{self.region} {self.tier} Token Plan key"}]}

    def synthesize(self, text, output_path, *, voice=None, model=None, speed=None, format="mp3", **extra):
        model, voice = model or self.default_model(), voice or self.default_voice()
        if model not in {row["id"] for row in self.list_models()} or voice != VOICE:
            raise ValueError("Unsupported Token Plan TTS model/voice; use the native catalogue and longanlingxin")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise ValueError(f"Token Plan TTS requires 1..{MAX_TEXT} characters; Hermes owns long-form chunking")
        if speed not in (None, 1, 1.0):
            raise ValueError("Token Plan TTS currently supports only speed 1.0")
        if format not in {"mp3", "wav", "ogg", "opus", "flac"}:
            raise ValueError("Unsupported TTS output format")
        key = self._key()
        if not key:
            raise ValueError(f"Set {self.key_names[-1]} for the selected Token Plan region and tier")
        try:
            from websockets.sync.client import connect
        except ImportError:
            raise RuntimeError("Token Plan TTS needs websockets >=14,<17 in the Hermes environment") from None
        task_id = uuid.uuid4().hex
        audio = bytearray()
        started = False
        deadline = time.monotonic() + TIMEOUT
        try:
            with connect(f"wss://{HOSTS[self.region]}/api-ws/v1/inference",
                         additional_headers={"Authorization": f"Bearer {key}"},
                         open_timeout=10, close_timeout=2, max_size=1024 * 1024,
                         max_queue=4, compression=None) as ws:
                def send(action, payload):
                    ws.send(json.dumps({"header": {"action": action, "task_id": task_id, "streaming": "duplex"}, "payload": payload}))
                send("run-task", {"task_group": "audio", "task": "tts", "function": "SpeechSynthesizer", "model": model,
                                  "parameters": {"text_type": "PlainText", "voice": voice, "format": "mp3", "sample_rate": 22050}, "input": {}})
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    message = ws.recv(timeout=remaining)
                    if isinstance(message, bytes):
                        if not started or len(audio) + len(message) > MAX_AUDIO:
                            raise RuntimeError("Invalid or oversized TTS audio")
                        audio.extend(message)
                        continue
                    event = json.loads(message)
                    header = event.get("header", {})
                    if header.get("task_id") != task_id:
                        raise RuntimeError("Mismatched TTS task")
                    kind = header.get("event")
                    if kind == "task-failed":
                        # Never echo server messages, which may contain text or credentials.
                        raise RuntimeError("Token Plan rejected synthesis; check region/tier entitlement, quota and model-specific voice")
                    if kind == "task-started":
                        if started:
                            raise RuntimeError("Duplicate TTS start")
                        started = True
                        send("continue-task", {"input": {"text": text}})
                        send("finish-task", {"input": {}})
                    elif kind == "task-finished":
                        if not started or not audio:
                            raise RuntimeError("Empty or incomplete TTS audio")
                        break
        except Exception:
            raise RuntimeError("Token Plan TTS failed or timed out; check credentials, entitlement/quota, voice and connection. No automatic retry was made.") from None
        # Commit output only after successful completion; preserve existing files on failure.
        target = Path(output_path).with_suffix(".mp3")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".mp3", delete=False) as file:
                temporary = file.name
                file.write(audio)
            os.replace(temporary, target)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        return str(target)
