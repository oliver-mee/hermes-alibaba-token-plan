"""Release assets are immutable source pins, with no consent or secret seeds."""
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
render = runpy.run_path(str(ROOT / "scripts/build-release-pack.py"))["render"]


@pytest.mark.parametrize("ref", ["main", "v1.6.0", "abc1234", "0" * 39, "g" * 40, "../main"])
def test_pack_ref_must_be_immutable(ref):
    with pytest.raises(ValueError):
        render(ref)


def test_release_pack_matches_both_component_versions():
    sha = "a" * 40
    pack = render(sha)
    assert pack.count(f"ref: {sha}") == 2
    assert "subdir: alibaba-token-plan\n" in pack
    assert "subdir: alibaba-token-plan-media\n" in pack
    assert 'version: "1.6.0"' in pack
    assert "config:" not in pack and "requires_env:" not in pack
    for name in ("alibaba-token-plan", "alibaba-token-plan-media"):
        assert "version: 1.6.0" in (ROOT / name / "plugin.yaml").read_text()
