"""Real directory-plugin discovery and normal file transcription; synthetic keys only."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERMES = os.environ.get("HERMES_AGENT_REPO", "")
pytestmark = pytest.mark.skipif(not HERMES, reason="Set HERMES_AGENT_REPO for native integration")


@pytest.mark.parametrize("with_chat", [False, True], ids=["media-alone", "chat-and-media"])
def test_native_asr_registration_and_dispatch(tmp_path, with_chat):
    home = tmp_path / "home"
    plugins = home / "plugins"
    shutil.copytree(ROOT / "alibaba-token-plan-media", plugins / "alibaba-token-plan-media")
    if with_chat:
        shutil.copytree(ROOT / "alibaba-token-plan", plugins / "model-providers/alibaba-token-plan")
    (home / "config.yaml").write_text('plugins:\n  enabled: [alibaba-token-plan-media]\nstt:\n  enabled: true\n  provider: alibaba-token-plan-asr\n  language: en\n  alibaba-token-plan-asr:\n    language: auto\n')
    # Do not inherit operator credentials, dotenv locations, hooks or profile settings.
    env = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
    env.update(HOME=str(home), HERMES_HOME=str(home), PYTHONPATH=str(Path(HERMES).resolve()),
               ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY="synthetic-test-only")
    probe = r'''
import io
import wave
import subprocess
import shutil
from pathlib import Path
from unittest.mock import patch
from hermes_cli.plugins import PluginManager
from agent.transcription_registry import get_provider
from tools import transcription_tools
manager = PluginManager()
manager.discover_and_load()
# Enabling one package loads all four native registries together. Only the root
# media manifest is discovered, including when no chat sibling is installed.
expected = {'alibaba-token-plan-media'}
if (Path.home() / 'plugins/model-providers/alibaba-token-plan').is_dir():
    expected.add('model-providers/alibaba-token-plan')
user_plugins = {key for key, info in manager._plugins.items() if info.manifest.source == 'user'}
assert user_plugins == expected, user_plugins
from agent import image_gen_registry, video_gen_registry, tts_registry
assert len(image_gen_registry.get_provider('alibaba-token-plan').list_models()) == 2
assert len(image_gen_registry.get_provider('alibaba-token-plan-team').list_models()) == 4
assert len(video_gen_registry.get_provider('alibaba-token-plan').list_models()) == 4
for name in ('alibaba-token-plan', 'alibaba-token-plan-team', 'alibaba-token-plan-cn', 'alibaba-token-plan-cn-team'):
    tts = tts_registry.get_provider(name)
    assert tts.default_model() == 'qwen-audio-3.0-tts-plus'
    assert not tts.streams_pcm
assert manager._plugins['alibaba-token-plan-media'].enabled, manager._plugins['alibaba-token-plan-media'].error
provider = get_provider('alibaba-token-plan-asr')
assert provider is not None
assert not provider.streaming_capable
try:
    provider.open_stream_session()
except NotImplementedError:
    pass
else:
    raise AssertionError('Streaming must be unsupported')
path = Path.home() / 'recording.wav'
with wave.open(str(path), 'wb') as audio:
    audio.setnchannels(1)
    audio.setsampwidth(2)
    audio.setframerate(16000)
    audio.writeframes(b'\x01\x00' * 16000)
import json
import http.client
import socket
calls = []
class Response:
    status = 200
    def __init__(self): self.read = io.BytesIO(b'{"output":{"text":"hello"}}').read
class Connection:
    def __init__(self, host, timeout):
        assert host == 'token-plan.maas.qwencloudapi.com'
    def request(self, method, route, **kwargs):
        assert kwargs['headers']['Authorization'] == 'Bearer synthetic-test-only'
        calls.append(json.loads(kwargs['body']))
    def getresponse(self): return Response()
    def close(self): pass
def deny_network(*args, **kwargs):
    raise AssertionError('Network forbidden in offline test')
with patch.object(http.client, 'HTTPSConnection', Connection), patch.object(socket, 'create_connection', deny_network):
    result = transcription_tools.transcribe_audio(str(path))
assert result['success'], result
assert result['transcript'] == 'hello', result
assert result['provider'] == provider.name
assert len(calls) == 1
# Real local conversion for a Telegram-like Ogg/Opus voice note, still mocked HTTP.
if shutil.which('ffmpeg') and shutil.which('ffprobe'):
    ogg = path.with_suffix('.ogg')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-c:a', 'libopus', str(ogg)], check=True)
    with patch.object(http.client, 'HTTPSConnection', Connection), patch.object(socket, 'create_connection', deny_network):
        converted = transcription_tools.transcribe_audio(str(ogg), source='gateway')
    assert converted['success'], converted
    assert len(calls) == 2
else:
    print('Ogg conversion: NOT RUN (ffmpeg/ffprobe absent)')
assert calls[0]['model'] == 'qwen-audio-3.0-asr-flash'
# Host hooks must not silently lose unsupported hints or send unsupported fields.
before = len(calls)
with patch.object(http.client, 'HTTPSConnection', Connection), patch.object(socket, 'create_connection', deny_network):
    with patch.object(transcription_tools, '_apply_pre_transcription_hook', return_value=(None, 'zh-HK', 'names')):
        hinted = transcription_tools.transcribe_audio(str(path))
    assert not hinted['success'] and hinted['error_kind'] == 'invalid_request', hinted
    assert len(calls) == before
    with patch.object(transcription_tools, '_apply_pre_transcription_hook', return_value=('other-model', 'auto', None)):
        invalid_model = transcription_tools.transcribe_audio(str(path))
    assert not invalid_model['success'] and len(calls) == before
    # One failed request must not poison the next native dispatch.
    with patch.object(Response, 'status', 429):
        quota = transcription_tools.transcribe_audio(str(path))
    assert not quota['success'] and quota['error_kind'] == 'quota', quota
    recovered = transcription_tools.transcribe_audio(str(path))
    assert recovered['success'], recovered
assert len(calls) == before + 2
# Real core guard refuses a synthetic protected file before decoding/upload.
protected = Path.home() / '.env'
protected.write_bytes(path.read_bytes())
with patch.object(http.client, 'HTTPSConnection', Connection), patch.object(socket, 'create_connection', deny_network):
    refused = provider.transcribe(str(protected))
assert not refused['success'] and 'Core file safety' in refused['error'], refused
assert len(calls) == before + 2
assert protected.read_bytes() == path.read_bytes()
# The file-only protocol whitelist alone is insufficient: concat can read other
# local files. Exercise the demuxer restriction with the real installed decoder.
if shutil.which('ffmpeg') and shutil.which('ffprobe'):
    playlist = path.with_name('playlist.wav')
    playlist.write_text("ffconcat version 1.0\nfile '" + str(path) + "'\n")
    with patch.object(http.client, 'HTTPSConnection', Connection), patch.object(socket, 'create_connection', deny_network):
        refused = provider.transcribe(str(playlist))
    assert not refused['success'] and refused['error_kind'] == 'invalid_request', refused
    assert len(calls) == before + 2 and playlist.exists() and path.exists()
from tools.transcription_streaming import streaming_available, open_streaming_session
stream_config = {'provider': provider.name, 'streaming': True,
                 provider.name: {'language': 'auto'}}
assert not streaming_available(stream_config)
assert open_streaming_session(stt_config=stream_config) is None
assert path.exists()  # the original recording remains for file fallback
# A namespace cannot shadow the built-in handlers.
assert transcription_tools._dispatch_to_plugin_provider(str(path), 'groq') is None
print('Native discovery and transcribe_audio dispatch: PASS')
'''
    result = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env,
                            text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dispatch: PASS" in result.stdout
