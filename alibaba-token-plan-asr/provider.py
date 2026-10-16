"""Bounded synchronous ASR over the Token Plan multimodal HTTP route."""
from __future__ import annotations

import base64
import http.client
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import wave

from agent.secret_scope import get_secret
from agent.file_safety import get_read_block_error
from agent.transcription_provider import TranscriptionProvider
from tools.transcription_audio import _find_ffmpeg_binary, _find_ffprobe_binary

class ASRError(ValueError):
    """Safe, locally authored error message."""

    def __init__(self, message, kind="invalid_request"):
        super().__init__(message)
        self.kind = kind


MAX_SOURCE = 25 * 1024 * 1024
MAX_WAV = 7 * 1024 * 1024  # base64 plus JSON stays below 10 MB
MAX_SECONDS = 180
MAX_RESPONSE = 1024 * 1024
# Exclude playlists/concat demuxers, which can read additional local files even
# with a file-only protocol whitelist. Keep ordinary voice-note containers.
DEMUXERS = "wav,mp3,ogg,flac,aac,mov,matroska,webm,aiff,au,amr"
ROUTE = "/api/v1/services/aigc/multimodal-generation/generation"
# Match the chat plugin's legacy-first Personal credential precedence.
KEYS = ("QWEN_TOKEN_PLAN_API_KEY", "BAILIAN_TOKEN_PLAN_API_KEY",
        "ALIBABA_TOKEN_PLAN_API_KEY", "ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY")


def catalogue():
    path = Path(__file__).resolve().parent.parent / "model-providers" / "alibaba-token-plan" / "fallback_models.py"
    if not path.is_file():  # source checkout, not the installed layout
        path = Path(__file__).resolve().parent.parent / "alibaba-token-plan" / "fallback_models.py"
    spec = importlib.util.spec_from_file_location("token_plan_asr_catalogue", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [{"id": row[0], "display": row[0]} for row in module.MEDIA_MODELS if row[1] == "asr"]


def read_source(file_path):
    """Open without following a final symlink or blocking on a FIFO; bound the snapshot."""
    if get_read_block_error(str(Path(file_path).absolute())):
        # Core diagnostics contain the path; expose only this fixed message.
        raise ASRError("Core file safety refused this protected audio input")
    fd = os.open(file_path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_SOURCE:
            raise ASRError("Audio must be a nonempty regular file of at most 25 MiB")
        data = source.read(MAX_SOURCE + 1)
        if len(data) > MAX_SOURCE:
            raise ASRError("Audio exceeds 25 MiB")
        after = os.fstat(source.fileno())
        if (len(data) != info.st_size or after.st_size != info.st_size
                or after.st_mtime_ns != info.st_mtime_ns):
            raise ASRError("Audio changed while reading; retry with a finished recording")
    return data


def wav_duration(data):
    with wave.open(io.BytesIO(data), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
            raise ASRError("WAV must be mono 16 kHz signed 16-bit PCM")
        frames = audio.getnframes()
        if not 0 < frames <= MAX_SECONDS * 16000:
            raise ASRError("Audio must be between 0 and 180 seconds")
        if len(audio.readframes(frames)) != frames * 2:
            raise ASRError("Truncated WAV")
        return frames / 16000


def normalise(file_path):
    data = read_source(file_path)
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        if int.from_bytes(data[4:8], "little") + 8 > len(data):
            raise ASRError("Truncated WAV")
        try:
            with wave.open(io.BytesIO(data), "rb") as audio:
                native = (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        except wave.Error:
            native = False  # e.g. float WAV: allow the bounded decoder below
        if native:
            # Do not repair a truncated/overlong PCM recording into a partial upload.
            wav_duration(data)
            if len(data) <= MAX_WAV:
                return data
    ffmpeg, ffprobe = _find_ffmpeg_binary(), _find_ffprobe_binary()
    if not ffmpeg or not ffprobe:
        raise ASRError("Audio conversion requires existing ffmpeg and ffprobe; nothing was installed", "dependency")
    with tempfile.TemporaryDirectory(prefix="token-plan-asr-") as directory:
        source, output = Path(directory) / "input", Path(directory) / "audio.wav"
        source.write_bytes(data)
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-protocol_whitelist", "file", "-format_whitelist", DEMUXERS,
             "-show_entries", "format=duration",
             "-of", "json", str(source)], stdin=subprocess.DEVNULL, capture_output=True, timeout=15, check=True)
        duration = float(json.loads(probe.stdout)["format"]["duration"])
        if not math.isfinite(duration) or not 0 < duration <= MAX_SECONDS:
            raise ASRError("Audio must be between 0 and 180 seconds")
        subprocess.run(
            [ffmpeg, "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file",
             "-format_whitelist", DEMUXERS, "-i", str(source),
             "-map", "0:a:0", "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
             "-t", str(MAX_SECONDS + 1), "-fs", str(MAX_WAV), str(output)],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=True)
        data = output.read_bytes()
        if len(data) > MAX_WAV:
            raise ASRError("Encoded audio exceeds upload limit")
        wav_duration(data)
        return data


def post(payload, key):
    """Single attempt, fixed host, no redirects, bounded response, no error-body leakage."""
    connection = http.client.HTTPSConnection("token-plan.maas.qwencloudapi.com", timeout=60)
    try:
        connection.request("POST", ROUTE, body=json.dumps(payload), headers={
            "Authorization": "Bearer " + key, "Content-Type": "application/json",
            "X-DashScope-SSE": "disable"})
        response = connection.getresponse()
        if response.status != 200:
            reason = {401: "credential rejected", 403: "entitlement denied", 429: "quota or rate limit"}.get(response.status, "upstream failure")
            kind = {401: "credential", 403: "entitlement", 429: "quota"}.get(response.status, "upstream")
            raise ASRError(f"ASR HTTP {response.status}: {reason}; no retry was made", kind)
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ASRError("ASR response exceeds 1 MiB", "response")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ASRError("ASR response must be an object", "response")
        if result.get("code") or result.get("error"):
            raise ASRError("ASR returned an upstream error; no retry was made", "upstream")
        return result
    except TimeoutError:
        raise ASRError("ASR request timed out; completion unknown, no retry was made", "timeout") from None
    except (OSError, http.client.HTTPException):
        raise ASRError("ASR connection failed; completion unknown, no retry was made", "network") from None
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, ASRError):
            raise
        raise ASRError("ASR returned malformed JSON", "response") from None
    finally:
        connection.close()


def extract_transcript(payload):
    if not isinstance(payload, dict):
        raise ASRError("ASR response must be an object", "response")
    output = payload.get("output")
    if not isinstance(output, dict):
        raise ASRError("ASR response is missing output", "response")
    text = output.get("text")
    if text is None:
        nested = output.get("output", {})
        sentence = nested.get("sentence", {}) if isinstance(nested, dict) else {}
        text = sentence.get("text") if isinstance(sentence, dict) else None
    if not isinstance(text, str):
        raise ASRError("ASR response is missing a transcript", "response")
    return text.strip()  # explicit empty transcript is valid silence


class TokenPlanASR(TranscriptionProvider):
    @property
    def name(self):
        return "alibaba-token-plan-asr"

    @property
    def display_name(self):
        return "Token Plan ASR (Global Personal)"

    def list_models(self):
        return catalogue()

    def is_available(self):
        try:
            return any(get_secret(key) for key in KEYS)
        except Exception:
            return False

    def get_setup_schema(self):
        return {"name": self.display_name, "badge": "paid",
                "tag": "File transcription; historical Global Personal evidence only",
                "env_vars": [{"key": KEYS[-1], "prompt": "Global Personal Token Plan key",
                              "url": "https://www.qwencloud.com/"}]}

    def transcribe(self, file_path, *, model=None, language=None, **extra):
        try:
            model = model or self.default_model()
            if model not in {item["id"] for item in self.list_models()}:
                raise ASRError("Unsupported Token Plan ASR model")
            if language not in (None, "", "auto") or extra.get("prompt"):
                raise ASRError("Language and prompt hints are unverified for this exact model; set stt.alibaba-token-plan-asr.language: auto and clear stt.prompt / pre_transcription prompt hints")
            key = next((value for name in KEYS if (value := get_secret(name))), None)
            if not key:
                raise ASRError("Set ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY (Global Personal); no PAYG fallback", "credential")
            audio = normalise(file_path)
            payload = {"model": model, "input": {"messages": [{"role": "user", "content": [
                {"type": "input_audio", "input_audio": {"data": "data:audio/wav;base64," + base64.b64encode(audio).decode("ascii")}}
            ]}]}, "parameters": {"format": "wav", "sample_rate": "16000"}}
            transcript = extract_transcript(post(payload, key))
            return {"success": True, "transcript": transcript, "provider": self.name}
        except ASRError as exc:
            # Only our fixed validation messages may reach callers, never server bodies/paths.
            message = str(exc)
            kind = exc.kind
        except subprocess.TimeoutExpired:
            message, kind = "Audio conversion timed out; no upload was made", "timeout"
        except (subprocess.CalledProcessError, OSError, ValueError, EOFError, wave.Error):
            message, kind = "Audio could not be read or decoded safely; no upload was made", "invalid_request"
        except Exception:
            message = "ASR failed (input, conversion, network or response); no automatic retry was made"
            kind = "availability"
        return {"success": False, "transcript": "", "provider": self.name, "error": message, "error_kind": kind}
