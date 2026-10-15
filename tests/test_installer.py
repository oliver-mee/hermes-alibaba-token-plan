"""Acceptance tests for the safe installer transaction."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "install.sh"


def run_installer(home: Path, *args: str, env: dict[str, str] | None = None):
    process_env = os.environ.copy()
    process_env["HERMES_HOME"] = str(home)
    if env:
        process_env.update(env)
    return subprocess.run(
        [str(INSTALLER), *args],
        cwd=REPO,
        env=process_env,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def run_installer_with_default_home(home: Path, *args: str):
    process_env = os.environ.copy()
    process_env.pop("HERMES_HOME", None)
    process_env["HOME"] = str(home)
    return subprocess.run(
        [str(INSTALLER), *args],
        cwd=REPO,
        env=process_env,
        text=True,
        capture_output=True,
        timeout=15,
        check=False,
    )


def plugin_root(home: Path) -> Path:
    return home / "plugins" / "model-providers"


def test_unset_hermes_home_defaults_to_dot_hermes(tmp_path: Path):
    fake_home = tmp_path / "user-home"
    fake_home.mkdir()

    installed = run_installer_with_default_home(fake_home)

    assert installed.returncode == 0, installed.stderr
    assert (
        plugin_root(fake_home / ".hermes")
        / "alibaba-token-plan"
        / "__init__.py"
    ).is_file()
    assert not (fake_home / "plugins").exists()


def test_install_upgrade_legacy_migration_verify_and_uninstall(tmp_path: Path):
    home = tmp_path / "hermes"
    legacy = plugin_root(home) / "alibaba-token-plan-cn"
    legacy.mkdir(parents=True)
    (legacy / "legacy-marker").write_text("legacy")

    installed = run_installer(home)
    assert installed.returncode == 0, installed.stderr
    assert (plugin_root(home) / "alibaba-token-plan" / "__init__.py").is_file()
    assert not legacy.exists()
    assert list((plugin_root(home) / ".backups").glob("alibaba-token-plan-cn.*"))

    verified = run_installer(home, "--verify")
    assert verified.returncode == 0, verified.stderr

    target_init = plugin_root(home) / "alibaba-token-plan" / "__init__.py"
    target_init.write_text("# stale installation\n")
    upgraded = run_installer(home)
    assert upgraded.returncode == 0, upgraded.stderr
    assert target_init.read_text() == (REPO / "alibaba-token-plan" / "__init__.py").read_text()
    assert list((plugin_root(home) / ".backups").glob("alibaba-token-plan.*"))

    removed = run_installer(home, "--uninstall")
    assert removed.returncode == 0, removed.stderr
    assert not (plugin_root(home) / "alibaba-token-plan").exists()
    assert run_installer(home, "--uninstall").returncode == 0


def test_failed_verification_rolls_back_both_directories(tmp_path: Path):
    home = tmp_path / "hermes"
    root = plugin_root(home)
    current = root / "alibaba-token-plan"
    legacy = root / "alibaba-token-plan-cn"
    current.mkdir(parents=True)
    legacy.mkdir()
    (current / "old-marker").write_text("main")
    (legacy / "old-marker").write_text("legacy")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cmp = fake_bin / "cmp"
    fake_cmp.write_text("#!/bin/sh\nexit 1\n")
    fake_cmp.chmod(0o755)

    result = run_installer(home, env={"PATH": f"{fake_bin}:{os.environ['PATH']}"})
    assert result.returncode != 0
    assert (current / "old-marker").read_text() == "main"
    assert (legacy / "old-marker").read_text() == "legacy"


def test_symlinked_destination_and_backup_are_rejected(tmp_path: Path):
    outside = tmp_path / "outside"
    outside.mkdir()

    destination_home = tmp_path / "destination-home"
    (destination_home / "plugins").mkdir(parents=True)
    (destination_home / "plugins" / "model-providers").symlink_to(outside)
    assert run_installer(destination_home).returncode == 2
    assert not any(outside.iterdir())

    backup_home = tmp_path / "backup-home"
    root = plugin_root(backup_home)
    root.mkdir(parents=True)
    (root / ".backups").symlink_to(outside)
    assert run_installer(backup_home).returncode == 2
    assert not any(outside.iterdir())


def test_relative_hermes_home_is_normalized(tmp_path: Path):
    home = tmp_path / "relative-home"
    relative_home = Path(os.path.relpath(home, REPO))

    installed = run_installer(relative_home)

    assert installed.returncode == 0, installed.stderr
    assert (plugin_root(home) / "alibaba-token-plan" / "__init__.py").is_file()


def test_asr_additive_install_verify_backup_and_uninstall(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    config = home / "config.yaml"
    config.write_text("stt:\n  provider: local\nplugins:\n  enabled: [other-plugin]\n")
    original = config.read_bytes()
    assert run_installer(home).returncode == 0
    target = home / "plugins/alibaba-token-plan-asr"
    assert (target / "provider.py").is_file()
    assert not (target / "__pycache__").exists()
    assert run_installer(home, "--verify").returncode == 0
    (target / "provider.py").write_text("old")
    assert run_installer(home, "--verify").returncode != 0
    assert run_installer(home).returncode == 0
    assert any(p.read_text() == "old" for p in (home / "plugins/.backups").glob("asr-upgrade.*/plugin/provider.py"))
    assert run_installer(home, "--uninstall").returncode == 0
    assert not target.exists()
    assert list((home / "plugins/.backups").glob("asr-removed.*/plugin/provider.py"))
    assert config.read_bytes() == original


def test_asr_symlink_target_is_rejected(tmp_path):
    home = tmp_path / "home"
    (home / "plugins").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (home / "plugins/alibaba-token-plan-asr").symlink_to(outside)
    assert run_installer(home).returncode == 2
    assert not any(outside.iterdir())


def test_asr_failed_verify_restores_previous_plugin(tmp_path):
    home = tmp_path / "home"
    target = home / "plugins/alibaba-token-plan-asr"
    target.mkdir(parents=True)
    (target / "old-marker").write_text("preserved")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_cmp = fake_bin / "cmp"
    fake_cmp.write_text("#!/bin/sh\nexit 1\n")
    fake_cmp.chmod(0o755)
    env = os.environ.copy()
    env.update(HERMES_HOME=str(home), PATH=f"{fake_bin}:{os.environ['PATH']}")
    result = subprocess.run(["bash", str(REPO / "install-asr.sh")], env=env, capture_output=True)
    assert result.returncode != 0
    assert (target / "old-marker").read_text() == "preserved"
