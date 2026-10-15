"""Offline lifecycle and safety checks; synthetic secrets only."""
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def provider(monkeypatch):
    class Base:
        def default_model(self):
            return self.list_models()[0]['id']
        def default_voice(self):
            return self.list_voices()[0]['id']
    abc = types.ModuleType('agent.tts_provider')
    abc.TTSProvider = Base
    monkeypatch.setitem(sys.modules, 'agent.tts_provider', abc)
    spec = importlib.util.spec_from_file_location('native_tts_test', ROOT / 'alibaba-token-plan-tts/provider.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.original_key = module.TokenPlanTTSProvider._key
    monkeypatch.setattr(module.TokenPlanTTSProvider, '_key', lambda self: 'synthetic')
    return module


class Socket:
    def __init__(self, events):
        self.events = iter(events)
        self.sent = []
        self.closed = False
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.closed = True
    def send(self, data):
        self.sent.append(json.loads(data))
    def recv(self, timeout):
        item = next(self.events)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, str):
            return json.dumps({'header': {'event': item, 'task_id': self.sent[0]['header']['task_id']}})
        return item


def transport(monkeypatch, socket):
    calls = []
    client = types.ModuleType('websockets.sync.client')
    def connect(*args, **kw):
        calls.append((args, kw))
        return socket
    client.connect = connect
    monkeypatch.setitem(sys.modules, 'websockets.sync.client', client)
    return calls


def test_synthesis_protocol_and_formats(provider, monkeypatch, tmp_path):
    ws = Socket(['task-started', b'ID3audio', 'task-finished'])
    calls = transport(monkeypatch, ws)
    p = provider.TokenPlanTTSProvider('cn', 'team')
    path = p.synthesize('Hello 世界', str(tmp_path / 'voice.ogg'), format='opus')
    assert Path(path).suffix == '.mp3'
    assert Path(path).read_bytes() == b'ID3audio'
    assert ws.closed
    assert calls[0][0] == ('wss://token-plan.maas.qianwenaiapi.com/api-ws/v1/inference',)
    assert calls[0][1]['max_queue'] == 4
    assert [x['header']['action'] for x in ws.sent] == ['run-task', 'continue-task', 'finish-task']
    assert ws.sent[0]['payload']['parameters'] == {'text_type': 'PlainText', 'voice': 'longanlingxin', 'format': 'mp3', 'sample_rate': 22050}
    assert ws.sent[1]['payload']['input']['text'] == 'Hello 世界'
    assert not p.streams_pcm and p.stream_sample_rate is None


@pytest.mark.parametrize('kw', [{'voice': 'Cherry'}, {'model': 'cosyvoice-v1'}, {'speed': 1.2}, {'format': 'pcm'}])
def test_unsupported_before_submission(provider, kw, tmp_path):
    with pytest.raises(ValueError):
        provider.TokenPlanTTSProvider().synthesize('hello', str(tmp_path / 'x.mp3'), **kw)


@pytest.mark.parametrize('events', [
    ['task-failed'], ['task-finished'], ['task-started', 'task-finished'],
    [b'early'], [TimeoutError('private-secret')], [KeyboardInterrupt()],
    ['task-started', 'task-started'], ['task-started', b'x' * 20],
])
def test_failure_cleanup_preserves_output(provider, monkeypatch, tmp_path, events):
    monkeypatch.setattr(provider, 'MAX_AUDIO', 10)
    ws = Socket(events)
    calls = transport(monkeypatch, ws)
    target = tmp_path / 'x.mp3'
    target.write_bytes(b'original')
    with pytest.raises((RuntimeError, KeyboardInterrupt)) as exc:
        provider.TokenPlanTTSProvider().synthesize('hello', str(target))
    assert 'private-secret' not in str(exc.value)
    assert ws.closed and len(calls) == 1
    assert target.read_bytes() == b'original'
    assert list(tmp_path.iterdir()) == [target]


def test_key_namespace_and_catalogue(provider, monkeypatch):
    for region in ('global', 'cn'):
        for tier in ('personal', 'team'):
            p = provider.TokenPlanTTSProvider(region, tier)
            assert p.list_models()[0]['id'] == 'qwen-audio-3.0-tts-plus'
            assert 'DASHSCOPE_API_KEY' not in p.key_names
            assert ('CN_' in p.key_names[-1]) == (region == 'cn')
            assert ('TEAM_' in p.key_names[-1]) == (tier == 'team')


@pytest.mark.parametrize('text', ['', '  ', 'x' * 2001])
def test_text_bounds(provider, text, tmp_path):
    with pytest.raises(ValueError):
        provider.TokenPlanTTSProvider().synthesize(text, str(tmp_path / 'x.mp3'))


def test_missing_key(provider, monkeypatch, tmp_path):
    monkeypatch.setattr(provider.TokenPlanTTSProvider, '_key', lambda self: '')
    with pytest.raises(ValueError, match='PERSONAL_API_KEY'):
        provider.TokenPlanTTSProvider().synthesize('hi', str(tmp_path / 'x.mp3'))


def test_native_secret_resolver_is_region_and_tier_isolated(provider, monkeypatch):
    calls = []
    helper = types.ModuleType('tools.tool_backend_helpers')
    def resolve(name, pool):
        calls.append((name, pool))
        return 'synthetic' if name == 'ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY' else ''
    helper.resolve_provider_secret = resolve
    monkeypatch.setitem(sys.modules, 'tools.tool_backend_helpers', helper)
    # Retrieve the original method hidden by the fixture patch.
    assert provider.original_key(provider.TokenPlanTTSProvider('cn', 'team')) == 'synthetic'
    assert calls == [('ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY', '')]
