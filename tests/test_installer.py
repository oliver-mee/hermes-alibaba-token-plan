"""Offline acceptance tests for the package-wide installer transaction."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "install.sh"
CHAT_FILES = ("__init__.py", "plugin.yaml", "fallback_models.py", "LICENSE")
MEDIA_FILES = (
    "__init__.py", "plugin.yaml", "fallback_models.py", "LICENSE",
    "THIRD-PARTY-NOTICES-ASR.txt", "video/__init__.py", "video/catalogue.py",
    "video/LICENSE", "image/__init__.py", "image/media.py", "image/catalogue.json",
    "image/LICENSE", "tts/__init__.py", "tts/provider.py", "asr/__init__.py", "asr/provider.py",
)


def run_installer(home: Path, *args: str, env=None, installer=INSTALLER):
    # Deliberately avoid inheriting keys or a user's runtime home.
    process_env = {"PATH": os.environ["PATH"], "HOME": str(home.parent / "user-home"),
                   "HERMES_HOME": str(home), "LC_ALL": "C"}
    if env:
        process_env.update(env)
    return subprocess.run(["bash", str(installer), *args], cwd=REPO, env=process_env,
                          text=True, capture_output=True, timeout=30, check=False)


def plugin_root(home):
    return home / "plugins/model-providers"


def targets(home):
    return (plugin_root(home) / "alibaba-token-plan",
            home / "plugins/alibaba-token-plan-media",
            plugin_root(home) / "alibaba-token-plan-cn")


def snapshot(home):
    """Original owned, sibling and config bytes; recovery copies are separate."""
    return {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*")
            if p.is_file() and ".backups" not in p.parts
            and not any(x.startswith(".token-plan.install.") for x in p.parts)}


def seed(home):
    for i, target in enumerate(targets(home)):
        target.mkdir(parents=True)
        (target / "original").write_bytes(f"old-component-{i}".encode())
    sibling = home / "plugins/unrelated"
    sibling.mkdir()
    (sibling / "plugin.yaml").write_text("enabled: true\n")
    (home / "config.yaml").write_text("plugins:\n  enabled: [unrelated]\ntts:\n  provider: edge\n")
    (home / ".env").write_text("SYNTHETIC_ONLY=fixture\n")


@pytest.fixture
def source_copy(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for file in ("install.sh", "install-asr.sh", "LICENSE", "THIRD-PARTY-NOTICES-ASR.txt"):
        shutil.copy2(REPO / file, source / file)
    for component in ("alibaba-token-plan", "alibaba-token-plan-media"):
        shutil.copytree(REPO / component, source / component,
                        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    return source


def test_clean_install_inventory_and_defaults(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    config = home / "config.yaml"
    config.write_text("plugins:\n  enabled: []\nmodel: existing\n")
    before = config.read_bytes()
    result = run_installer(home)
    assert result.returncode == 0, result.stderr
    for target, files in zip(targets(home), (CHAT_FILES, MEDIA_FILES)):
        assert {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()} == set(files)
    assert run_installer(home, "--verify").returncode == 0
    assert config.read_bytes() == before
    assert not list(home.rglob("__pycache__"))


def test_unset_and_relative_hermes_home(tmp_path):
    fake_home = tmp_path / "user"
    env = {"HOME": str(fake_home), "HERMES_HOME": ""}
    assert run_installer(tmp_path / "ignored", env=env).returncode == 0
    assert targets(fake_home / ".hermes")[0].is_dir()
    home = tmp_path / "relative"
    result = run_installer(Path(os.path.relpath(home, REPO)))
    assert result.returncode == 0, result.stderr
    assert targets(home)[1].is_dir()


def test_v156_upgrade_legacy_retirement_and_uninstall_backups(tmp_path):
    home = tmp_path / "home"
    seed(home)
    (targets(home)[0] / "plugin.yaml").write_text("version: 1.5.6\n")
    config = (home / "config.yaml").read_bytes()
    assert run_installer(home).returncode == 0
    assert not targets(home)[2].exists()
    for name, root in (("alibaba-token-plan", plugin_root(home)),
                       ("alibaba-token-plan-cn", plugin_root(home)),
                       ("alibaba-token-plan-media", home / "plugins")):
        assert list((root / ".backups").glob(name + ".*/original"))
    assert run_installer(home, "--verify").returncode == 0
    assert run_installer(home, "--uninstall").returncode == 0
    assert not any(p.exists() for p in targets(home))
    assert list((home / "plugins/.backups").glob("alibaba-token-plan-media.*/asr/provider.py"))
    assert (home / "config.yaml").read_bytes() == config
    assert (home / "plugins/unrelated/plugin.yaml").read_text() == "enabled: true\n"
    assert run_installer(home, "--uninstall").returncode == 0


@pytest.mark.parametrize("component,file", [(0, "fallback_models.py"), (1, "asr/provider.py"),
                                           (1, "video/LICENSE"), (1, "THIRD-PARTY-NOTICES-ASR.txt")])
def test_corruption_detected_and_repaired(tmp_path, component, file):
    home = tmp_path / "home"
    assert run_installer(home).returncode == 0
    (targets(home)[component] / file).write_text("corrupted")
    assert run_installer(home, "--verify").returncode != 0
    assert run_installer(home).returncode == 0
    assert run_installer(home, "--verify").returncode == 0


@pytest.mark.parametrize("path", ["plugins", "plugins/model-providers", "plugins/.backups",
    "plugins/model-providers/.backups", "plugins/model-providers/alibaba-token-plan",
    "plugins/alibaba-token-plan-media", "plugins/model-providers/alibaba-token-plan-cn"])
def test_destination_symlinks_rejected(tmp_path, path):
    outside = tmp_path / "outside"
    outside.mkdir()
    home = tmp_path / "home"
    destination = home / path
    destination.parent.mkdir(parents=True)
    destination.symlink_to(outside, target_is_directory=True)
    assert run_installer(home).returncode == 2
    assert not list(outside.iterdir())


@pytest.mark.parametrize("kind", ["home", "ancestor", "dotdot"])
def test_home_ancestor_symlinks_rejected(tmp_path, kind):
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(outside, target_is_directory=True)
    home = {"home": linked, "ancestor": linked / "home", "dotdot": linked / ".." / "home"}[kind]
    assert run_installer(home).returncode == 2
    assert not list(outside.iterdir())


@pytest.mark.parametrize("component", ["alibaba-token-plan", "alibaba-token-plan-media"])
@pytest.mark.parametrize("kind", ["missing", "symlink", "fifo", "ancestor"])
def test_unsafe_or_incomplete_source_fails_before_mutation(tmp_path, source_copy, component, kind):
    home = tmp_path / "home"
    seed(home)
    before = snapshot(home)
    source = source_copy / component / "plugin.yaml"
    source.unlink()
    if kind == "symlink":
        source.symlink_to(REPO / component / "plugin.yaml")
    elif kind == "fifo":
        os.mkfifo(source)
    elif kind == "ancestor":
        shutil.rmtree(source_copy / component)
        (source_copy / component).symlink_to(REPO / component, target_is_directory=True)
    result = run_installer(home, installer=source_copy / "install.sh")
    assert result.returncode == 2, result.stderr
    assert snapshot(home) == before
    assert not list(home.rglob(".backups"))
    assert not list(home.rglob(".token-plan.install.*"))


def test_symlinked_source_ancestor_rejected(tmp_path, source_copy):
    link = tmp_path / "linked-source"
    link.symlink_to(source_copy, target_is_directory=True)
    home = tmp_path / "home"
    assert run_installer(home, installer=link / "install.sh").returncode == 2
    assert not home.exists()


@pytest.mark.parametrize("component", [0, 1])
@pytest.mark.parametrize("kind", ["symlink", "fifo"])
def test_unsafe_installed_contents_rejected(tmp_path, component, kind):
    home = tmp_path / "home"
    assert run_installer(home).returncode == 0
    target = targets(home)[component] / "plugin.yaml"
    target.unlink()
    if kind == "symlink":
        target.symlink_to(REPO / "alibaba-token-plan/plugin.yaml")
    else:
        os.mkfifo(target)
    for action in ("install", "--verify", "--uninstall"):
        assert run_installer(home, action).returncode == 2


@pytest.mark.parametrize("preview", ["video_gen/alibaba-token-plan-video", "image_gen/alibaba-token-plan-image",
    "alibaba-token-plan-video", "alibaba-token-plan-image", "alibaba-token-plan-tts", "alibaba-token-plan-asr"])
def test_preview_requires_explicit_migration(tmp_path, preview):
    home = tmp_path / "home"
    seed(home)
    old = home / "plugins" / preview
    old.mkdir(parents=True)
    (old / "original").write_text("preview-enabled")
    before = snapshot(home)
    result = run_installer(home)
    assert result.returncode == 2
    assert "Migration required" in result.stderr and "disable" in result.stderr
    assert snapshot(home) == before
    assert not list(home.rglob(".backups"))


def inject_failure(tmp_path, command, condition):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    wrapper = fake_bin / command
    wrapper.write_text(f'#!/bin/bash\nif {condition}; then exit 1; fi\nexec /bin/{command} "$@"\n')
    wrapper.chmod(0o755)
    return {"PATH": f"{fake_bin}:{os.environ['PATH']}"}


@pytest.mark.parametrize("component", [0, 1])
@pytest.mark.parametrize("operation", ["copy", "stage-verify", "swap", "installed-verify", "backup"])
def test_failure_at_each_component_restores_entire_package(tmp_path, component, operation):
    home = tmp_path / "home"
    seed(home)
    before = snapshot(home)
    name = ("alibaba-token-plan", "alibaba-token-plan-media")[component]
    target = str(targets(home)[component])
    if operation == "copy":
        command, condition = "cp", f'[[ "$1" == */{name}/__init__.py ]]'
    elif operation == "stage-verify":
        command, condition = "cmp", f'[[ "$3" == */.token-plan.install.*/{component}/__init__.py ]]'
    elif operation == "swap":
        command, condition = "mv", f'[[ "$1" == */.token-plan.install.*/{component} && "$2" == "{target}" ]]'
    elif operation == "installed-verify":
        command, condition = "cmp", f'[[ "$3" == "{target}/__init__.py" ]]'
    else:
        command, condition = "mv", f'[[ "$1" == "{target}" && "$2" == */.backups/* ]]'
    result = run_installer(home, env=inject_failure(tmp_path, command, condition))
    assert result.returncode != 0, result.stdout
    assert snapshot(home) == before
    assert not list(home.rglob(".token-plan.install.*"))


@pytest.mark.parametrize("action", ["install", "--uninstall"])
def test_failed_legacy_move_restores_both_components(tmp_path, action):
    home = tmp_path / "home"
    seed(home)
    before = snapshot(home)
    result = run_installer(home, action, env=inject_failure(tmp_path, "mv",
        '[[ "$1" == */alibaba-token-plan-cn && "$2" == */.backups/* ]]'))
    assert result.returncode != 0
    assert snapshot(home) == before


def test_uninstall_needs_no_source_payload(tmp_path, source_copy):
    home = tmp_path / "home"
    assert run_installer(home).returncode == 0
    shutil.rmtree(source_copy / "alibaba-token-plan-media")
    assert run_installer(home, "--uninstall", installer=source_copy / "install.sh").returncode == 0


@pytest.mark.parametrize("native_chat", ["alibaba-token-plan-provider", "alibaba-token-plan"])
def test_flat_native_chat_blocks_duplicate_install(tmp_path, native_chat):
    home = tmp_path / "home"
    seed(home)
    native = home / "plugins" / native_chat
    native.mkdir()
    (native / "plugin.yaml").write_text("native-owned")
    before = snapshot(home)
    result = run_installer(home)
    assert result.returncode == 2
    assert "native/flat chat" in result.stderr
    assert snapshot(home) == before


@pytest.mark.parametrize("record", ['{"alibaba-token-plan-media": {}}',
    '{"alibaba-token-plan-provider": {}}', '{"alibaba-token-plan": {}}',
    '{"alibaba-token-plan-medi\\u0061": {}}', 'broken-json', '[]'])
def test_native_ownership_or_invalid_metadata_blocks_mutation(tmp_path, record):
    home = tmp_path / "home"
    seed(home)
    (home / "plugins/.install-metadata.json").write_text(record)
    before = snapshot(home)
    for action in ("install", "--verify", "--uninstall"):
        result = run_installer(home, action)
        assert result.returncode == 2
        assert "native" in result.stderr
        assert snapshot(home) == before


def test_unrelated_native_metadata_preserved(tmp_path):
    home = tmp_path / "home"
    seed(home)
    metadata = home / "plugins/.install-metadata.json"
    metadata.write_text('{"unrelated": {"source": "synthetic-fixture"}}\n')
    before = metadata.read_bytes()
    assert run_installer(home).returncode == 0
    assert metadata.read_bytes() == before
    assert run_installer(home, "--uninstall").returncode == 0
    assert metadata.read_bytes() == before


@pytest.mark.parametrize("component", [0, 1])
def test_uninstall_failure_rolls_back_all_original_bytes(tmp_path, component):
    home = tmp_path / "home"
    seed(home)
    before = snapshot(home)
    target = str(targets(home)[component])
    result = run_installer(home, "--uninstall", env=inject_failure(tmp_path, "mv",
        f'[[ "$1" == "{target}" && "$2" == */.backups/* ]]'))
    assert result.returncode != 0
    assert snapshot(home) == before


def test_failed_recovery_preserves_original_in_backup_and_reports_path(tmp_path):
    home = tmp_path / "home"
    seed(home)
    env = inject_failure(tmp_path, "mv",
        '[[ "$1" == */.token-plan.install.*/1 || "$1" == */.backups/alibaba-token-plan.* ]]')
    result = run_installer(home, env=env)
    assert result.returncode != 0
    assert "recovery move failed" in result.stderr
    originals = list((plugin_root(home) / ".backups").glob("alibaba-token-plan.*/original"))
    assert len(originals) == 1
    assert originals[0].read_bytes() == b"old-component-0"
    assert (targets(home)[1] / "original").read_bytes() == b"old-component-1"
    assert (targets(home)[2] / "original").read_bytes() == b"old-component-2"
    assert list(home.rglob(".token-plan.install.*"))
