"""Real Hermes loader + speech-tool dispatcher, mocked WebSocket only."""
import os
import shutil
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HERMES = os.environ.get('HERMES_AGENT_REPO', '')


@pytest.mark.skipif(not HERMES, reason='Set HERMES_AGENT_REPO for native Hermes integration')
def test_native_loader_and_speech_tool(tmp_path):
    home = tmp_path / 'hermes'
    home.mkdir()
    subprocess.run([str(ROOT / 'install.sh')], env={**os.environ, 'HERMES_HOME': str(home)}, check=True, capture_output=True)
    (home / 'config.yaml').write_text('plugins:\n  enabled: [alibaba-token-plan-tts]\n')
    fixture = tmp_path / 'fixture.mp3'
    if shutil.which('ffmpeg'):
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'sine=frequency=440:sample_rate=22050:duration=0.1',
                        '-codec:a', 'libmp3lame', str(fixture)], check=True, timeout=15)
    code = r'''
import json
from pathlib import Path
from unittest.mock import patch
import sys
import socket
def deny_network(*args, **kwargs):
    raise AssertionError('Unexpected network access in offline native integration')
socket.socket.connect = deny_network
from hermes_cli.plugins import PluginManager
from agent import tts_registry
manager = PluginManager()
manager.discover_and_load()
info = manager._plugins['alibaba-token-plan-tts']
assert info.enabled, info.error
p = tts_registry.get_provider('alibaba-token-plan')
assert p is not None
assert len(tts_registry.list_providers()) == 4
assert p.default_model() == 'qwen-audio-3.0-tts-plus'
assert p.default_voice() == 'longanlingxin'
assert not p.streams_pcm
from tools import tts_tool
from tools.tts_tool_delivery import _resolve_max_text_length
from tools.tts_streaming import resolve_streaming_provider
cfg = {'provider': p.name, 'voice': 'longanlingxin', p.name: {'max_text_length': 2000}}
assert _resolve_max_text_length(p.name, cfg) == 2000
audio = b'ID3mock-audio'
class Socket:
    def __init__(self): self.sent=[]; self.i=0; self.closed=False
    def __enter__(self): return self
    def __exit__(self,*a): self.closed=True
    def send(self,data): self.sent.append(json.loads(data))
    def recv(self,timeout):
        self.i += 1
        if self.i == 2: return audio
        return json.dumps({'header': {'task_id': self.sent[0]['header']['task_id'], 'event': 'task-started' if self.i == 1 else 'task-finished'}})
ws=Socket()
with patch('websockets.sync.client.connect', return_value=ws), patch.object(tts_tool, '_load_tts_config', return_value=cfg):
    result=json.loads(tts_tool.text_to_speech_tool(text='Hello 世界', output_path=sys.argv[1]))
assert result['success'], result
assert Path(result['file_path']).read_bytes() == b'ID3mock-audio'
assert ws.closed
assert [x['header']['action'] for x in ws.sent] == ['run-task','continue-task','finish-task']
assert tts_tool._plugin_provider_is_voice_compatible(p.name)
# All namespaces dispatch through Hermes with the same configured voice/rate;
# neither native streaming resolver nor the plugin invents a PCM capability.
for name in ('alibaba-token-plan', 'alibaba-token-plan-team', 'alibaba-token-plan-cn', 'alibaba-token-plan-cn-team'):
    selected = tts_registry.get_provider(name)
    assert [v['id'] for v in selected.list_voices()] == ['longanlingxin', 'longanlufeng']
    selected_cfg = {**cfg, 'provider': name, 'voice': 'longanlufeng', 'speed': 1.25}
    assert resolve_streaming_provider(selected_cfg) is None
    ws = Socket()
    with patch('websockets.sync.client.connect', return_value=ws) as connect, patch.object(tts_tool, '_load_tts_config', return_value=selected_cfg):
        result = json.loads(tts_tool.text_to_speech_tool(text='Hi 世界', output_path=str(Path(sys.argv[1]).with_name(name + '.mp3'))))
    assert result['success'], result
    params = ws.sent[0]['payload']['parameters']
    assert params['voice'] == 'longanlufeng' and params['rate'] == 1.25
    assert ('qianwenaiapi.com' in connect.call_args.args[0]) == ('-cn' in name)
    assert ws.closed
# The same native dispatcher backs automatic replies and per-sentence CLI/Desktop audio.
if Path(sys.argv[2]).is_file():
    audio = Path(sys.argv[2]).read_bytes()
    with patch('websockets.sync.client.connect', side_effect=lambda *a, **kw: Socket()), patch.object(tts_tool, '_load_tts_config', return_value=cfg), patch.object(tts_tool, '_session_platform', return_value=('telegram', True)):
        delivered = json.loads(tts_tool.text_to_speech_tool(text='Hello.', output_path=str(Path(sys.argv[1]).with_name('telegram.ogg'))))
    assert delivered['success'], delivered
    assert delivered['voice_compatible']
    assert Path(delivered['file_path']).read_bytes().startswith(b'OggS')
    print('synthetic MP3 through native Telegram Opus delivery: PASS')
    sockets = []
    def fresh(*a, **kw):
        socket = Socket()
        sockets.append(socket)
        return socket
    with patch('websockets.sync.client.connect', side_effect=fresh), patch.object(tts_tool, '_load_tts_config', return_value=cfg):
        long_result = json.loads(tts_tool.text_to_speech_tool(text='A' * 2100, output_path=str(Path(sys.argv[1]).with_name('long.mp3'))))
    assert long_result['success'], long_result
    assert long_result['chunk_count'] == 2
    assert [len(s.sent[1]['payload']['input']['text']) for s in sockets] == [2000, 100]

print('native loader + text_to_speech tool: PASS')
'''
    # Never inherit real API keys or HOME credential stores into the subprocess.
    env = {k: v for k, v in os.environ.items() if 'KEY' not in k and 'TOKEN' not in k and 'SECRET' not in k}
    env.update(HOME=str(tmp_path), HERMES_HOME=str(home), PYTHONPATH=HERMES)
    for name in ('PERSONAL', 'TEAM', 'CN_PERSONAL', 'CN_TEAM'):
        env[f'ALIBABA_TOKEN_PLAN_{name}_API_KEY'] = 'synthetic'
    proc = subprocess.run([sys.executable, '-c', code, str(tmp_path / 'out.mp3'), str(fixture)], env=env, cwd=HERMES, capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert 'native loader + text_to_speech tool: PASS' in proc.stdout
    if fixture.is_file():
        assert 'synthetic MP3 through native Telegram Opus delivery: PASS' in proc.stdout
