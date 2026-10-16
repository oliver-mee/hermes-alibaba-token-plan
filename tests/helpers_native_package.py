"""Subprocess harness for test_native_package (not an alternate installer)."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(sys.argv[1])
SCENARIO = sys.argv[2]
COMPONENT = sys.argv[3]
HOME = Path(os.environ["HERMES_HOME"])
HOME.mkdir(exist_ok=True)
(HOME / "config.yaml").write_text("model: preserve-this-choice\nplugins:\n  enabled: []\n")
(HOME / ".env").write_text("UNRELATED_TEST_VALUE=preserve\n")
(HOME / "session-sentinel").write_bytes(b"user-session")

# Kernel filtering survives PM's `python -I` worker and compiled uv children,
# which deliberately discard PYTHONPATH/sitecustomize. macOS is sandboxed by
# the parent. Unix-domain sockets remain available on Linux.
downloads = SCENARIO in {"lifecycle", "pack"} and os.environ.get("HERMES_NATIVE_PACKAGE_DOWNLOADS") == "1"
if sys.platform.startswith("linux") and not downloads:
    import ctypes
    import ctypes.util
    import errno
    import socket
    library = ctypes.util.find_library("seccomp")
    if not library:
        raise RuntimeError("Native offline acceptance requires libseccomp on Linux")
    seccomp = ctypes.CDLL(library, use_errno=True)
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_syscall_resolve_name.restype = ctypes.c_int
    seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    class Compare(ctypes.Structure):
        _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                    ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]
    context = seccomp.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    assert context
    try:
        syscall = seccomp.seccomp_syscall_resolve_name(b"socket")
        assert syscall >= 0
        for family in (socket.AF_INET, socket.AF_INET6):
            assert seccomp.seccomp_rule_add(context, 0x50000 | errno.ENETUNREACH,
                                           syscall, 1, Compare(0, 4, family, 0)) == 0
        assert seccomp.seccomp_load(context) == 0
    finally:
        seccomp.seccomp_release(context)
elif sys.platform != "darwin" and not downloads:
    raise RuntimeError("Native offline package acceptance supports Linux/macOS")

# Guard subprocess network escape routes too: Git is local-only; unknown
# executables cannot bootstrap a downloader outside the Python socket guard.
# An actually prepared PM runtime must be supplied for offline acceptance.
def audit(event, args):
    if event != "subprocess.Popen":
        return
    executable, argv = str(args[0]), args[1]
    name = Path(executable).name.lower()
    if name == "git":
        if any(str(a).startswith(("https://", "http://", "ssh://", "git@")) for a in argv):
            raise RuntimeError("offline native package test: remote Git blocked")
    elif not (name.startswith("python") or (name in {"uv", "uvx"} and Path(executable).is_relative_to(HOME))):
        raise RuntimeError("offline native package test: unprepared external tool: " + name)
sys.addaudithook(audit)

print("Native lifecycle mode: public dependency downloads; no inference" if downloads else "Native package mode: strict offline", flush=True)
from hermes_cli import plugins_cmd as pc


def preserved():
    import hermes_yaml as yaml
    assert yaml.safe_load((HOME / "config.yaml").read_text())["model"] == "preserve-this-choice"
    assert (HOME / ".env").read_text() == "UNRELATED_TEST_VALUE=preserve\n"
    assert (HOME / "session-sentinel").read_bytes() == b"user-session"


def load_package(path, name):
    spec = importlib.util.spec_from_file_location(name, path / "__init__.py",
                                                 submodule_search_locations=[str(path)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


if SCENARIO == "admission":
    from hermes_cli.plugin_validate import validate_plugin_dir
    # Only the requested subdirectory is present; no sibling import can hide
    # a missing file/dependency in the published component.
    candidate = Path.cwd() / COMPONENT
    shutil.copytree(ROOT / COMPONENT, candidate, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    report = validate_plugin_dir(candidate)
    print(json.dumps(report.to_dict(), indent=2))
    assert report.ok, report.failures
    preserved()
    sys.exit(0)

if SCENARIO == "collision":
    flat = HOME / "plugins/alibaba-token-plan-provider"
    category = HOME / "plugins/model-providers/alibaba-token-plan"
    for path in (flat, category):
        shutil.copytree(ROOT / "alibaba-token-plan", path, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    candidate = flat if COMPONENT == "flat" else category
    try:
        load_package(candidate, "duplicate_chat_probe")
    except RuntimeError as exc:
        assert "Duplicate Token Plan chat installation" in str(exc), str(exc)
    else:
        raise AssertionError("Ambiguous shell/native chat import accepted")
    assert flat.is_dir() and category.is_dir()
    preserved()
    sys.exit(0)

# A genuine temporary Git repository supplies exact source bytes. All native
# clone/fetch, scanning, admission, publication and ledger code remains real.
fixture = Path.cwd() / "source"
fixture.mkdir()
for component in ("alibaba-token-plan", "alibaba-token-plan-media"):
    shutil.copytree(ROOT / component, fixture / component,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def git(*args):
    return subprocess.run(["git", "-C", str(fixture), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


git("init")
git("-c", "user.name=Offline Fixture", "-c", "user.email=fixture@example.invalid",
    "add", ".")
git("-c", "user.name=Offline Fixture", "-c", "user.email=fixture@example.invalid",
    "commit", "-m", "Snapshot exact component bytes")
first = git("rev-parse", "HEAD")
source = fixture.as_uri()


def install(component, **kwargs):
    return pc._install_plugin_core(source + "#" + component,
                                   force=kwargs.pop("force", False), **kwargs)


def discover_media(expected):
    from hermes_cli.plugins import PluginManager
    from agent import image_gen_registry, video_gen_registry, tts_registry, transcription_registry
    for registry in (image_gen_registry, video_gen_registry, tts_registry, transcription_registry):
        registry._reset_for_tests()
    manager = PluginManager()
    manager.discover_and_load()
    for registry in (image_gen_registry, video_gen_registry, tts_registry, transcription_registry):
        provider_name = "alibaba-token-plan-asr" if registry is transcription_registry else "alibaba-token-plan"
        assert (registry.get_provider(provider_name) is not None) == expected, registry.__name__
    return manager


if SCENARIO == "lifecycle":
    target, manifest, name = install(COMPONENT, ref=first)
    assert target.parent == HOME / "plugins"
    assert not (target / ".git").exists(), "Subdir installs carry provenance outside their tree"
    record = pc._read_install_metadata()[name]
    assert record == {"source": source + "#" + COMPONENT, "revision": first, "pinned": True}
    assert "catalog" not in record, "Pack repo pins are custom provenance"
    pc.cmd_disable(name)
    assert name in pc._get_disabled_set()
    if COMPONENT.endswith("media"):
        discover_media(False)
    pc.cmd_enable(name)
    assert name in pc._get_enabled_set() and name not in pc._get_disabled_set()
    if COMPONENT.endswith("media"):
        assert not (HOME / "plugins/alibaba-token-plan-provider").exists()
        discover_media(True)
    pc.cmd_disable(name)
    user_file = target / "user-state.json"
    user_file.write_text('{"preserve": true}\n')
    install(COMPONENT, force=True)  # Retains original pin without --ref.
    assert user_file.read_text() == '{"preserve": true}\n'
    assert pc._read_install_metadata()[name]["revision"] == first
    from hermes_cli.plugins_cmd_update import _pull_plugin_update
    try:
        _pull_plugin_update(target, lambda rec: "pinned-refusal", lambda: "not-git")
    except pc.PluginOperationError as exc:
        assert str(exc) == "pinned-refusal"
    else:
        raise AssertionError("Ordinary update moved a custom pin")
    (fixture / COMPONENT / "revision-marker.txt").write_text("second revision\n")
    git("add", ".")
    git("-c", "user.name=Offline Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-m", "Second fixture revision")
    second = git("rev-parse", "HEAD")
    install(COMPONENT, force=True, ref=second)
    assert (target / "revision-marker.txt").read_text() == "second revision\n"
    assert user_file.read_text() == '{"preserve": true}\n'
    assert pc._read_install_metadata()[name]["revision"] == second
    preserved()
    pc.cmd_remove(name)
    assert not target.exists() and name not in pc._read_install_metadata()
    assert name not in pc._get_enabled_set() and name not in pc._get_disabled_set()
    preserved()
    print("Real native pinned install/disable/enable/reinstall/refusal/re-pin/remove passed:", name)

elif SCENARIO == "pack":
    from hermes_cli.plugin_packs import PluginPack, PackPluginEntry, ResolvedPackPlugin, install_pack_plugins
    # The pack's owner/repo+subdir transport resolution alone is substituted
    # with a local Git URL; install/consent/admission fan-out remains upstream.
    entries = [PackPluginEntry(repo="fixture/components", subdir=c, ref=first)
               for c in ("alibaba-token-plan", "alibaba-token-plan-media", "absent-component")]
    pack = PluginPack(name="offline-two-components", plugins=entries)
    resolved = [ResolvedPackPlugin(entry=e, identifier=source + "#" + e.subdir) for e in entries]
    results = install_pack_plugins(pack, resolved, pc._console())
    assert [r.ok for r in results] == [True, True, False], results
    names = {r.installed_name for r in results if r.ok}
    assert names == {"alibaba-token-plan-provider", "alibaba-token-plan-media"}
    metadata = pc._read_install_metadata()
    assert set(metadata) == names
    for record in metadata.values():
        assert record["revision"] == first and record["pinned"] is True
        assert "catalog" not in record
    discovered = [row[0] for row in pc._discover_all_plugins()]
    assert all(discovered.count(name) == 1 for name in names)
    discover_media(True)
    import providers
    assert providers.get_provider_profile("alibaba-token-plan") is not None
    preserved()
    print("Real pack: two namespaces retained after third entry failed")
else:
    raise AssertionError(SCENARIO)
