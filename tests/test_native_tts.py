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


@pytest.mark.parametrize('kw', [{'voice': 'Cherry'}, {'model': 'cosyvoice-v1'}, {'speed': 2.1}, {'format': 'pcm'}])
def test_unsupported_before_submission(provider, kw, tmp_path):
    with pytest.raises(ValueError):
        provider.TokenPlanTTSProvider().synthesize('hello', str(tmp_path / 'x.mp3'), **kw)


@pytest.mark.parametrize('events', [
    ['task-failed'], ['task-finished'], ['task-started', 'task-finished'],
    [b'early'], [TimeoutError('private-secret')], [KeyboardInterrupt()],
    ['task-started', 'task-started'], ['task-started', b'x' * 20],
    ['task-started', b'partial', 'task-failed'],
    ['task-started', b'partial', OSError('private-secret')],
    ['task-started', b'partial'],
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


def test_native_metadata_is_local_and_model_specific(provider, monkeypatch):
    def no_key(self):
        pytest.fail('Catalogue/setup must not read credentials')
    monkeypatch.setattr(provider.TokenPlanTTSProvider, '_key', no_key)
    for region in ('global', 'cn'):
        for tier in ('personal', 'team'):
            p = provider.TokenPlanTTSProvider(region, tier)
            assert p.default_voice() == 'longanlingxin'
            assert [v['id'] for v in p.list_voices()] == ['longanlingxin', 'longanlufeng']
            assert all(v['language'] == 'zh, en' for v in p.list_voices())
            setup = p.get_setup_schema()
            assert setup['env_vars'][0]['key'] == p.key_names[-1]
            expected_url = 'https://www.qwencloud.com/' if region == 'global' else 'https://www.qianwenai.com/'
            assert setup['env_vars'][0]['url'] == expected_url
    # A future catalogue addition must not inherit this model's voices/protocol.
    monkeypatch.setattr(provider, '_models', lambda: [('unimplemented-tts', 'tts', ('personal',), ('global',))])
    assert provider.TokenPlanTTSProvider().list_models() == []


@pytest.mark.parametrize('voice', ['longanlingxin', 'longanlufeng'])
@pytest.mark.parametrize('speed', [0.5, 1.0, 1.25, 2.0])
def test_voice_and_speed_wire_contract(provider, monkeypatch, tmp_path, voice, speed):
    ws = Socket(['task-started', b'ID3audio', 'task-finished'])
    transport(monkeypatch, ws)
    provider.TokenPlanTTSProvider().synthesize('Hello 世界', str(tmp_path / 'voice.mp3'), voice=voice, speed=speed)
    params = ws.sent[0]['payload']['parameters']
    assert params['voice'] == voice
    assert params.get('rate', 1.0) == speed
    assert 'speed' not in params


@pytest.mark.parametrize('kw', [
    {'voice': 'longanlingxi'}, {'voice': 'longanhuan_v3.6'}, {'voice': 'longanlingxin_v3.1'},
    {'voice': ''}, {'model': ''}, {'speed': True}, {'speed': '1.0'},
    {'speed': float('nan')}, {'speed': float('inf')}, {'speed': 0.49},
])
def test_invalid_controls_never_connect(provider, monkeypatch, tmp_path, kw):
    calls = transport(monkeypatch, Socket([]))
    with pytest.raises(ValueError):
        provider.TokenPlanTTSProvider().synthesize('hello', str(tmp_path / 'voice.mp3'), **kw)
    assert not calls and not list(tmp_path.iterdir())


@pytest.mark.parametrize('events,diagnostic', [
    (['task-failed'], 'rejected synthesis'),
    (['task-started', TimeoutError('private-text')], 'timed out'),
    (['task-started', OSError('private-key')], 'connection or protocol'),
])
def test_safe_actionable_errors(provider, monkeypatch, tmp_path, events, diagnostic):
    ws = Socket(events)
    calls = transport(monkeypatch, ws)
    with pytest.raises(RuntimeError, match=diagnostic) as exc:
        provider.TokenPlanTTSProvider().synthesize('private-text', str(tmp_path / 'x.mp3'))
    assert 'private-' not in str(exc.value)
    assert ws.closed and len(calls) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('message', [
    'not JSON', '[]', 'null', '{"header":[]}',
    '{"header":{"task_id":"other", "event":"task-started"}}',
])
def test_malformed_events_are_sanitised(provider, monkeypatch, tmp_path, message):
    class RawSocket(Socket):
        def recv(self, timeout):
            return message
    ws = RawSocket([])
    transport(monkeypatch, ws)
    with pytest.raises(RuntimeError):
        provider.TokenPlanTTSProvider().synthesize('hi', str(tmp_path / 'x.mp3'))
    assert ws.closed and not list(tmp_path.iterdir())


@pytest.mark.parametrize('events', [['unknown'], ['result-generated'], ['task-started', 'unknown']])
def test_unexpected_protocol_event(provider, monkeypatch, tmp_path, events):
    ws = Socket(events)
    transport(monkeypatch, ws)
    with pytest.raises(RuntimeError, match='Unexpected'):
        provider.TokenPlanTTSProvider().synthesize('hi', str(tmp_path / 'x.mp3'))
    assert ws.closed and not list(tmp_path.iterdir())


def test_result_metadata_does_not_enter_artifact_or_logs(provider, monkeypatch, tmp_path, caplog):
    class ResultSocket(Socket):
        def recv(self, timeout):
            value = super().recv(timeout)
            if isinstance(value, str) and 'result-generated' in value:
                event = json.loads(value)
                event['payload'] = {'output': {'original_text': 'private-text'}}
                return json.dumps(event)
            return value
    ws = ResultSocket(['task-started', 'result-generated', b'ID3audio', 'task-finished'])
    calls = transport(monkeypatch, ws)
    with caplog.at_level('DEBUG'):
        path = provider.TokenPlanTTSProvider().synthesize('private-text', str(tmp_path / 'x.mp3'))
        calls[0][1]['logger'].debug('private-key private-text')
    assert Path(path).read_bytes() == b'ID3audio'
    assert 'private-' not in caplog.text
    assert calls[0][1]['logger'].propagate is False


@pytest.mark.parametrize('kind', ['requested-symlink', 'mp3-symlink', 'directory', 'fifo'])
def test_unsafe_output_fails_before_submission(provider, monkeypatch, tmp_path, kind):
    import os
    target = tmp_path / 'out.mp3'
    requested = tmp_path / 'out.ogg'
    if kind.endswith('symlink'):
        victim = tmp_path / 'victim'
        victim.write_bytes(b'preserve')
        (requested if kind == 'requested-symlink' else target).symlink_to(victim)
    elif kind == 'directory':
        target.mkdir()
    else:
        os.mkfifo(target)
    calls = transport(monkeypatch, Socket([]))
    with pytest.raises(ValueError, match='regular file'):
        provider.TokenPlanTTSProvider().synthesize('hello', str(requested))
    assert not calls
    if kind.endswith('symlink'):
        assert victim.read_bytes() == b'preserve'


def test_unwritable_artifact_fails_before_submission(provider, monkeypatch, tmp_path):
    calls = transport(monkeypatch, Socket([]))
    def fail(**kw):
        raise PermissionError('private-path')
    monkeypatch.setattr(provider.tempfile, 'NamedTemporaryFile', fail)
    with pytest.raises(RuntimeError, match='Cannot prepare') as exc:
        provider.TokenPlanTTSProvider().synthesize('hello', str(tmp_path / 'x.mp3'))
    assert not calls and 'private-' not in str(exc.value)


def test_replace_failure_preserves_previous_artifact(provider, monkeypatch, tmp_path):
    ws = Socket(['task-started', b'ID3audio', 'task-finished'])
    transport(monkeypatch, ws)
    target = tmp_path / 'x.mp3'
    target.write_bytes(b'previous')
    def fail(*args):
        raise OSError('private-path')
    monkeypatch.setattr(provider.os, 'replace', fail)
    with pytest.raises(RuntimeError, match='Cannot save') as exc:
        provider.TokenPlanTTSProvider().synthesize('hello', str(target))
    assert 'private-' not in str(exc.value)
    assert target.read_bytes() == b'previous' and list(tmp_path.iterdir()) == [target]


def test_deadline_and_interrupt_after_audio(provider, monkeypatch, tmp_path):
    ws = Socket(['task-started', b'ID3audio', KeyboardInterrupt()])
    calls = transport(monkeypatch, ws)
    with pytest.raises(KeyboardInterrupt):
        provider.TokenPlanTTSProvider().synthesize('hello', str(tmp_path / 'x.mp3'))
    assert ws.closed and len(calls) == 1 and not list(tmp_path.iterdir())
    ws = Socket(['task-started', b'ID3audio', 'task-finished'])
    calls = transport(monkeypatch, ws)
    times = iter([0, 1, 61])
    monkeypatch.setattr(provider.time, 'monotonic', lambda: next(times))
    with pytest.raises(RuntimeError, match='timed out'):
        provider.TokenPlanTTSProvider().synthesize('hello', str(tmp_path / 'x.mp3'))
    assert ws.closed and len(calls) == 1 and not list(tmp_path.iterdir())


def test_concurrent_calls_have_separate_tasks_and_artifacts(provider, monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    sockets, lock, barrier = [], Lock(), Barrier(3)
    client = types.ModuleType('websockets.sync.client')
    def connect(*args, **kw):
        ws = Socket(['task-started', b'ID3audio', 'task-finished'])
        with lock:
            sockets.append(ws)
        barrier.wait(timeout=5)
        return ws
    client.connect = connect
    monkeypatch.setitem(sys.modules, 'websockets.sync.client', client)
    p = provider.TokenPlanTTSProvider()
    with ThreadPoolExecutor(max_workers=3) as pool:
        paths = list(pool.map(lambda n: p.synthesize(str(n), str(tmp_path / f'{n}.mp3')), range(3)))
    assert len({ws.sent[0]['header']['task_id'] for ws in sockets}) == 3
    assert all(ws.closed for ws in sockets)
    assert all(Path(path).read_bytes() == b'ID3audio' for path in paths)
    assert len(list(tmp_path.iterdir())) == 3


@pytest.mark.parametrize('region,tier,names', [
    ('global', 'personal', ['QWEN_TOKEN_PLAN_API_KEY', 'BAILIAN_TOKEN_PLAN_API_KEY', 'ALIBABA_TOKEN_PLAN_API_KEY', 'ALIBABA_TOKEN_PLAN_PERSONAL_API_KEY']),
    ('global', 'team', ['ALIBABA_TOKEN_PLAN_TEAM_API_KEY']),
    ('cn', 'personal', ['ALIBABA_TOKEN_PLAN_CN_API_KEY', 'ALIBABA_TOKEN_PLAN_CN_PERSONAL_API_KEY']),
    ('cn', 'team', ['ALIBABA_TOKEN_PLAN_CN_TEAM_API_KEY']),
])
def test_scoped_key_alias_precedence(provider, monkeypatch, region, tier, names):
    calls = []
    helper = types.ModuleType('tools.tool_backend_helpers')
    values = {}
    def resolve(name, pool):
        calls.append((name, pool))
        return values.get(name, '')
    helper.resolve_provider_secret = resolve
    monkeypatch.setitem(sys.modules, 'tools.tool_backend_helpers', helper)
    p = provider.TokenPlanTTSProvider(region, tier)
    assert provider.original_key(p) == ''
    assert calls == [(name, '') for name in names]
    values.update({names[0]: 'legacy-or-canonical', names[-1]: 'canonical'})
    calls.clear()
    assert provider.original_key(p) == values[names[0]]
    assert calls == [(names[0], '')]


def test_old_host_registration_guard(tmp_path):
    # Importing/registering on a host without TTS must not import its missing ABC.
    spec = importlib.util.spec_from_file_location('tts_old_host', ROOT / 'alibaba-token-plan-tts/__init__.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.register(types.SimpleNamespace())


def test_real_websocket_library_on_loopback(provider, monkeypatch, tmp_path, caplog):
    """Exercise actual send/recv/header/close APIs, without any vendor connection."""
    from threading import Thread
    client = pytest.importorskip('websockets.sync.client')
    server_module = pytest.importorskip('websockets.sync.server')
    real_connect = client.connect
    received, failures = [], []
    def handler(ws):
        try:
            assert ws.request.headers['Authorization'] == 'Bearer synthetic'
            run = json.loads(ws.recv(timeout=3))
            received.append(run)
            task_id = run['header']['task_id']
            def event(name):
                ws.send(json.dumps({'header': {'task_id': task_id, 'event': name}}))
            event('task-started')
            received.extend([json.loads(ws.recv(timeout=3)), json.loads(ws.recv(timeout=3))])
            ws.send(b'ID3loopback')
            event('task-finished')
            # Client must close after success, rather than leaking a connection.
            assert list(ws) == []
        except Exception as exc:
            failures.append(exc)
    with server_module.serve(handler, '127.0.0.1', 0, logger=provider._WIRE_LOGGER) as server:
        port = server.socket.getsockname()[1]
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def local_connect(url, **kw):
            assert url == 'wss://token-plan.maas.qwencloudapi.com/api-ws/v1/inference'
            return real_connect(f'ws://127.0.0.1:{port}', **kw)
        monkeypatch.setattr(client, 'connect', local_connect)
        try:
            with caplog.at_level('DEBUG'):
                output = provider.TokenPlanTTSProvider().synthesize('private-text', str(tmp_path / 'out.mp3'))
            assert Path(output).read_bytes() == b'ID3loopback'
        finally:
            server.shutdown()
            thread.join(timeout=5)
    assert not failures and not thread.is_alive()
    assert [r['header']['action'] for r in received] == ['run-task', 'continue-task', 'finish-task']
    assert 'synthetic' not in caplog.text and 'private-text' not in caplog.text
    assert Path(output).stat().st_mode & 0o777 == 0o600
