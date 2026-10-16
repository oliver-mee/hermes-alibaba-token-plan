"""TTS and ASR ship together in the additive combined media component."""
from test_installer import REPO, run_installer, targets


def test_tts_asr_package_defaults_and_compatibility_entrypoint(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    config = home / "config.yaml"
    config.write_text("tts:\n  provider: edge\nstt:\n  provider: existing\nplugins:\n  enabled: []\n")
    before = config.read_bytes()
    entrypoint = REPO / "install-asr.sh"
    installed = run_installer(home, installer=entrypoint)
    assert installed.returncode == 0, installed.stderr
    media = targets(home)[1]
    assert (media / "tts/provider.py").is_file()
    assert (media / "asr/provider.py").is_file()
    assert (media / "THIRD-PARTY-NOTICES-ASR.txt").is_file()
    assert run_installer(home, "--verify", installer=entrypoint).returncode == 0
    assert config.read_bytes() == before
    assert run_installer(home, "--uninstall", installer=entrypoint).returncode == 0
    assert not targets(home)[0].exists() and not media.exists()
    assert config.read_bytes() == before


def test_asr_entrypoint_rejects_preview_without_mutation(tmp_path):
    home = tmp_path / "home"
    preview = home / "plugins/alibaba-token-plan-asr"
    preview.mkdir(parents=True)
    (preview / "marker").write_text("old")
    result = run_installer(home, installer=REPO / "install-asr.sh")
    assert result.returncode == 2
    assert "Migration required" in result.stderr
    assert (preview / "marker").read_text() == "old"
    assert not targets(home)[0].exists()
