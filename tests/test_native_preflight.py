"""Prevent ambiguous shell/native ownership without changing installation state."""
import json
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
check = runpy.run_path(str(ROOT / "scripts/check-native-install.py"))["problems"]


def test_fresh_and_native_managed_homes(tmp_path):
    assert check(tmp_path) == []
    plugins = tmp_path / "plugins"
    plugins.mkdir()
    (plugins / "alibaba-token-plan-provider").mkdir()
    (plugins / "alibaba-token-plan-media").mkdir()
    (plugins / ".install-metadata.json").write_text(json.dumps({
        name: {"source": "synthetic", "revision": "a" * 40}
        for name in ("alibaba-token-plan-provider", "alibaba-token-plan-media")}))
    assert check(tmp_path) == []


@pytest.mark.parametrize("component", ["model-providers/alibaba-token-plan", "model-providers/alibaba-token-plan-cn", "video_gen/alibaba-token-plan-video", "image_gen/alibaba-token-plan-image", "alibaba-token-plan-tts", "alibaba-token-plan-asr", "alibaba-token-plan-provider", "alibaba-token-plan-media"])
def test_existing_unmanaged_components_block_without_changes(tmp_path, component):
    path = tmp_path / "plugins" / component
    path.mkdir(parents=True)
    marker = path / "marker"
    marker.write_bytes(b"preserve")
    assert check(tmp_path)
    assert marker.read_bytes() == b"preserve"


def test_symlink_and_invalid_ledger_block(tmp_path):
    (tmp_path / "plugins").symlink_to(tmp_path / "elsewhere")
    assert "symlink" in check(tmp_path)[0]
    (tmp_path / "plugins").unlink()
    (tmp_path / "plugins").mkdir()
    ledger = tmp_path / "plugins/.install-metadata.json"
    ledger.write_text("[]")
    assert check(tmp_path)
    assert ledger.read_text() == "[]"
