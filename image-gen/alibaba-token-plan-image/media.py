"""Bounded image inputs and profile-local artifacts; no hosting service uploads."""
import base64
import binascii
import ipaddress
import os
from pathlib import Path
import socket
import stat
import tempfile
import time
from urllib.parse import urlsplit

MAX_SOURCE = 10 * 1024 * 1024
MAX_OUTPUT = 25 * 1024 * 1024
MEDIA_SECONDS = 60
MIME_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def image_type(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    raise ValueError("Only PNG, JPEG and WebP image signatures are supported")


def _https_url(url):
    if not isinstance(url, str) or len(url) > 8192:
        raise ValueError("Invalid image URL")
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError("Image URL must be public HTTPS without credentials or fragments")
    # Reject private addresses even when the host's global allow_private_urls is on.
    answers = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not answers or any(not ipaddress.ip_address(row[4][0]).is_global for row in answers):
        raise ValueError("Image URL must resolve only to public addresses")


def _download(url, cap):
    from tools.url_safety import create_ssrf_safe_client
    _https_url(url)
    deadline = time.monotonic() + MEDIA_SECONDS
    # Guarded Hermes transport validates DNS at connect; redirects are never followed.
    with create_ssrf_safe_client(timeout=30, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url) as response:
            if response.status_code != 200:
                raise ValueError("Image download failed or redirected")
            mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if mime not in MIME_EXT:
                raise ValueError("Image download has unsupported content type")
            length = response.headers.get("content-length")
            if length is not None and (not length.isdigit() or int(length) > cap):
                raise ValueError("Image download exceeds the plugin's byte cap")
            raw = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                if time.monotonic() > deadline:
                    raise ValueError("Image download exceeded its time limit")
                if len(raw) + len(chunk) > cap:
                    raise ValueError("Image download exceeds the plugin's byte cap")
                raw.extend(chunk)
    if image_type(raw) != mime:
        raise ValueError("Image signature does not match content type")
    return bytes(raw), mime


def source_image(source):
    if not isinstance(source, str) or not source:
        raise ValueError("Source image must be an HTTPS URL, data URI or absolute path")
    if source.startswith("https:"):
        return _download(source, MAX_SOURCE)
    if source.startswith("data:"):
        if len(source) > MAX_SOURCE * 4 // 3 + 128:
            raise ValueError("Inline source exceeds the plugin's 10 MiB safety cap")
        header, sep, encoded = source.partition(",")
        mime = header[5:].removesuffix(";base64")
        if not sep or mime not in MIME_EXT or not header.endswith(";base64"):
            raise ValueError("Source data URI must contain base64 PNG, JPEG or WebP")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("Invalid base64 source image") from None
        if len(raw) > MAX_SOURCE or image_type(raw) != mime:
            raise ValueError("Inline source has wrong type or exceeds the safety cap")
        return raw, mime
    path = Path(source).expanduser()
    if not path.is_absolute():
        raise ValueError("Source image path must be absolute")
    from agent.file_safety import raise_if_read_blocked
    # Apply Hermes's credential-file guard before reading, including resolved aliases.
    raise_if_read_blocked(str(path))
    raise_if_read_blocked(str(path.resolve()))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlinked image sources are not supported")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_SOURCE:
            raise ValueError("Source must be a non-empty regular image of at most 10 MiB")
        raw = stream.read(MAX_SOURCE + 1)
    if len(raw) > MAX_SOURCE:
        raise ValueError("Source exceeds the plugin's byte cap")
    return raw, image_type(raw)


def cache_image(url, prefix):
    from hermes_constants import get_hermes_home
    # Resolve per call, never at import time: concurrent routed profiles keep
    # separate files under their context-local home override.
    home = get_hermes_home().absolute()
    target = home / "cache/generated/images"
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError("Refusing symlinked image cache")
    target.mkdir(parents=True, exist_ok=True)
    raw, mime = _download(url, MAX_OUTPUT)
    fd, name = tempfile.mkstemp(prefix=f"{prefix}_", suffix=f".{MIME_EXT[mime]}", dir=target)
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise
