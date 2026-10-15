"""Additive media packaging must preserve user configuration and sibling plugins."""
from test_installer import run_installer, plugin_root


def test_tts_install_verify_upgrade_uninstall(tmp_path):
    home = tmp_path / 'home'
    home.mkdir()
    config = home / 'config.yaml'
    config.write_text('tts:\n  provider: edge\n')
    sibling = home / 'plugins/alibaba-token-plan-video'
    sibling.mkdir(parents=True)
    (sibling / 'marker').write_text('preserve')
    old_chat = plugin_root(home) / 'alibaba-token-plan'
    old_chat.mkdir(parents=True)
    (old_chat / 'plugin.yaml').write_text('version: 1.5.6\n')
    assert run_installer(home).returncode == 0
    tts = home / 'plugins/alibaba-token-plan-tts'
    assert (tts / 'provider.py').is_file()
    assert run_installer(home, '--verify').returncode == 0
    (tts / 'provider.py').write_text('stale')
    assert run_installer(home, '--verify').returncode != 0
    assert run_installer(home).returncode == 0
    assert list((plugin_root(home) / '.backups').glob('alibaba-token-plan-tts.*'))
    assert config.read_text() == 'tts:\n  provider: edge\n'
    assert run_installer(home, '--uninstall').returncode == 0
    assert not tts.exists()
    assert (sibling / 'marker').read_text() == 'preserve'
    assert config.read_text() == 'tts:\n  provider: edge\n'


def test_tts_symlink_rejected(tmp_path):
    home = tmp_path / 'home'
    (home / 'plugins').mkdir(parents=True)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (home / 'plugins/alibaba-token-plan-tts').symlink_to(outside)
    assert run_installer(home).returncode == 2
    assert not any(outside.iterdir())


def test_tts_copy_failure_restores_chat_and_tts(tmp_path):
    import os
    home = tmp_path / 'home'
    assert run_installer(home).returncode == 0
    chat = plugin_root(home) / 'alibaba-token-plan'
    tts = home / 'plugins/alibaba-token-plan-tts'
    (chat / 'old-marker').write_text('chat')
    (tts / 'old-marker').write_text('tts')
    fake_bin = tmp_path / 'bin'
    fake_bin.mkdir()
    cp = fake_bin / 'cp'
    cp.write_text('#!/bin/sh\ncase "$*" in *provider.py*) exit 1;; esac\nexec /bin/cp "$@"\n')
    cp.chmod(0o755)
    result = run_installer(home, env={'PATH': f'{fake_bin}:{os.environ["PATH"]}'})
    assert result.returncode != 0
    assert (chat / 'old-marker').read_text() == 'chat'
    assert (tts / 'old-marker').read_text() == 'tts'
