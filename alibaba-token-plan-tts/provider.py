"""DashScope run-task synthesis, one isolated connection per invocation.

Native integration pattern: Deepgram voice plugin (MIT, Jayson Santos dos Reis)
2d31b885 and Fish Audio Hermes (Apache-2.0, Electric Sheep) 4c987455.
No third-party implementation code is copied; see docs/native-tts.md.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import math
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
# Model-specific system voices, cross-checked against the pinned public wiki
# a76c7a7e and the vendor voice table on 2026-10-16. Only Lingxin has historical
# Token Plan synthesis evidence; catalogue membership is not live validation.
MODEL_VOICES = {"qwen-audio-3.0-tts-plus": (
    {"id": VOICE, "display": "Long An Ling Xin (historical synthesis 2026-09-08)",
     "language": "zh, en", "gender": "female"},
    {"id": "longanlufeng", "display": "Long An Lu Feng (documented; live check not run)",
     "language": "zh, en", "gender": "male"},
)}
HOSTS = {"global": "token-plan.maas.qwencloudapi.com", "cn": "token-plan.maas.qianwenaiapi.com"}

# websockets DEBUG logs include Authorization and text/audio frames. Give only
# this connection a silent logger; do not change the host's logging settings.
_WIRE_LOGGER = logging.Logger("token_plan_tts.private_transport")
_WIRE_LOGGER.addHandler(logging.NullHandler())
_WIRE_LOGGER.propagate = False


class _SynthesisError(RuntimeError):
    """Only fixed, public diagnostics may escape the transport boundary."""


def _check_target(target):
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise ValueError("Token Plan TTS output must be a regular file, not a symlink or special file")


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
                for row in _models() if row[1] == "tts" and row[0] in MODEL_VOICES
                and self.tier in row[2] and self.region in row[3]]

    def list_voices(self):
        return [dict(row) for row in MODEL_VOICES.get(self.default_model(), ())]

    def default_voice(self):
        return VOICE

    def get_setup_schema(self):
        return {"name": self.display_name, "badge": "subscription", "tag": "Whole-file MP3; region/tier entitlement must be checked",
                "env_vars": [{"key": self.key_names[-1], "prompt": f"{self.region} {self.tier} Token Plan key",
                              "url": "https://www.qwencloud.com/" if self.region == "global" else "https://www.qianwenai.com/"}]}

    def synthesize(self, text, output_path, *, voice=None, model=None, speed=None, format="mp3", **extra):
        model = self.default_model() if model is None else model
        voice = self.default_voice() if voice is None else voice
        if not isinstance(model, str) or model not in {row["id"] for row in self.list_models()}:
            raise ValueError("Unsupported Token Plan TTS model; use the native model catalogue")
        if not isinstance(voice, str) or voice not in {row["id"] for row in MODEL_VOICES[model]}:
            raise ValueError("Unsupported voice for this Token Plan TTS model; use the native voice catalogue")
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise ValueError(f"Token Plan TTS requires 1..{MAX_TEXT} characters; Hermes owns long-form chunking")
        if speed is not None and (isinstance(speed, bool) or not isinstance(speed, (int, float))
                                  or not math.isfinite(speed) or not 0.5 <= speed <= 2.0):
            raise ValueError("Token Plan TTS speed must be a finite number from 0.5 to 2.0")
        if format not in {"mp3", "wav", "ogg", "opus", "flac"}:
            raise ValueError("Unsupported TTS output format")
        key = self._key()
        if not key:
            raise ValueError(f"Set {self.key_names[-1]} for the selected Token Plan region and tier")
        try:
            from websockets.sync.client import connect
        except ImportError:
            raise RuntimeError("Token Plan TTS needs websockets >=14,<17 in the Hermes environment") from None
        # Reserve a private artifact before a paid submission, so invalid/unwritable
        # destinations fail locally. Do not overwrite an earlier result on error.
        target = Path(output_path).with_suffix(".mp3")
        _check_target(Path(output_path))
        _check_target(target)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            file = tempfile.NamedTemporaryFile(dir=target.parent, suffix=".mp3", delete=False)
        except OSError:
            raise RuntimeError("Cannot prepare Token Plan TTS output; check the destination and permissions") from None
        try:
            with file:
                audio = self._synthesize_audio(text, model, voice, speed, key)
                file.write(audio)
            _check_target(target)
            os.replace(file.name, target)
        except OSError:
            raise RuntimeError("Cannot save Token Plan TTS audio; check storage and permissions. No automatic retry was made.") from None
        finally:
            if os.path.exists(file.name):
                os.unlink(file.name)
        return str(target)

    def _synthesize_audio(self, text, model, voice, speed, key):
        from websockets.sync.client import connect
        task_id = uuid.uuid4().hex
        audio = bytearray()
        started = False
        deadline = time.monotonic() + TIMEOUT
        try:
            with connect(f"wss://{HOSTS[self.region]}/api-ws/v1/inference",
                         additional_headers={"Authorization": f"Bearer {key}"},
                         open_timeout=10, close_timeout=2, max_size=1024 * 1024,
                         max_queue=4, compression=None, logger=_WIRE_LOGGER) as ws:
                def send(action, payload):
                    ws.send(json.dumps({"header": {"action": action, "task_id": task_id, "streaming": "duplex"}, "payload": payload}))
                parameters = {"text_type": "PlainText", "voice": voice, "format": "mp3", "sample_rate": 22050}
                if speed is not None and speed != 1.0:
                    parameters["rate"] = float(speed)
                send("run-task", {"task_group": "audio", "task": "tts", "function": "SpeechSynthesizer", "model": model,
                                  "parameters": parameters, "input": {}})
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    message = ws.recv(timeout=remaining)
                    if isinstance(message, bytes):
                        if not started or len(audio) + len(message) > MAX_AUDIO:
                            raise _SynthesisError("Invalid or oversized Token Plan TTS audio; no output was saved")
                        audio.extend(message)
                        continue
                    event = json.loads(message)
                    if not isinstance(event, dict) or not isinstance(event.get("header"), dict):
                        raise _SynthesisError("Malformed Token Plan TTS event; no output was saved")
                    header = event.get("header", {})
                    if header.get("task_id") != task_id:
                        raise _SynthesisError("Mismatched Token Plan TTS task; no output was saved")
                    kind = header.get("event")
                    if kind == "task-failed":
                        # Never echo server messages, which may contain text or credentials.
                        raise _SynthesisError("Token Plan rejected synthesis; check the selected region/tier key, entitlement, quota and model-specific voice. No automatic retry was made.")
                    if kind == "task-started":
                        if started:
                            raise _SynthesisError("Duplicate Token Plan TTS start; no output was saved")
                        started = True
                        send("continue-task", {"input": {"text": text}})
                        send("finish-task", {"input": {}})
                    elif kind == "task-finished":
                        if not started or not audio:
                            raise _SynthesisError("Empty or incomplete Token Plan TTS audio; no output was saved")
                        break
                    elif kind != "result-generated" or not started:
                        raise _SynthesisError("Unexpected Token Plan TTS event; no output was saved")
        except _SynthesisError:
            raise
        except TimeoutError:
            raise RuntimeError("Token Plan TTS timed out; no output was saved. No automatic retry was made.") from None
        except Exception:
            raise RuntimeError("Token Plan TTS connection or protocol failed; check the connection and selected region/tier key. No automatic retry was made.") from None
        return audio
