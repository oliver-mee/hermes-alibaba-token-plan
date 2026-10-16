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


def test_native_image_upgrade_verify_uninstall_and_defaults(tmp_path):
    home = tmp_path / "hermes"
    home.mkdir()
    config = home / "config.yaml"
    original = "model: existing-chat\nimage_gen:\n  provider: existing-image\n"
    config.write_text(original)
    target = home / "plugins/image_gen/alibaba-token-plan-image"
    # Existing chat-only installation (v1.5.6 layout) and sibling providers.
    chat = plugin_root(home) / "alibaba-token-plan"
    chat.mkdir(parents=True)
    (chat / "old-marker").write_text("v1.5.6")
    sibling = home / "plugins/video_gen/other-provider"
    sibling.mkdir(parents=True)
    (sibling / "marker").write_text("preserve")
    assert run_installer(home).returncode == 0
    assert run_installer(home, "--verify").returncode == 0
    assert target.is_dir() and (target / "LICENSE").is_file()
    assert not list(target.rglob("__pycache__"))
    (target / "media.py").write_text("# stale")
    assert run_installer(home, "--verify").returncode != 0
    assert run_installer(home).returncode == 0
    backups = target.parent / ".backups"
    assert list(backups.glob("alibaba-token-plan-image.*"))
    assert run_installer(home, "--uninstall").returncode == 0
    assert not target.exists() and not chat.exists()
    assert config.read_text() == original and (sibling / "marker").read_text() == "preserve"


def test_image_failure_rolls_back_chat_and_image(tmp_path):
    home = tmp_path / "hermes"
    assert run_installer(home).returncode == 0
    image = home / "plugins/image_gen/alibaba-token-plan-image"
    chat = plugin_root(home) / "alibaba-token-plan"
    (image / "old-marker").write_text("image")
    (chat / "old-marker").write_text("chat")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    cmp = fake_bin / "cmp"
    cmp.write_text('#!/bin/sh\ncase "$*" in *media.py*) exit 1;; esac\nexec /usr/bin/cmp "$@"\n')
    cmp.chmod(0o755)
    result = run_installer(home, env={"PATH": f"{fake_bin}:{os.environ['PATH']}"})
    assert result.returncode != 0
    assert (image / "old-marker").read_text() == "image"
    assert (chat / "old-marker").read_text() == "chat"


def test_image_symlink_destinations_and_installed_files_rejected(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    for suffix in ("plugins/image_gen", "plugins/image_gen/.backups",
                   "plugins/image_gen/alibaba-token-plan-image"):
        home = tmp_path / suffix.replace("/", "-")
        target = home / suffix
        target.parent.mkdir(parents=True)
        target.symlink_to(outside)
        assert run_installer(home).returncode == 2
        assert not list(outside.iterdir())
    home = tmp_path / "installed"
    assert run_installer(home).returncode == 0
    file = home / "plugins/image_gen/alibaba-token-plan-image/media.py"
    file.unlink()
    file.symlink_to(outside / "not-source")
    assert run_installer(home, "--verify").returncode != 0
