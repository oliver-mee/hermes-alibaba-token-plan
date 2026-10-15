"""Media metadata travels with the plugin, without becoming a chat choice."""
import importlib.util
from pathlib import Path


def test_wan_media_and_retired_chat_separation():
    path = Path(__file__).resolve().parents[1] / 'alibaba-token-plan/fallback_models.py'
    spec = importlib.util.spec_from_file_location('catalogue', path)
    assert spec and spec.loader
    cat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cat)
    media = {row[0]: row for row in cat.MEDIA_MODELS}
    assert media['wan3.0-video'][1] == 'video'
    assert set(media['wan3.0-video'][2]) == {'personal', 'team'}
    assert set(media['wan3.0-video'][3]) == {'global', 'cn'}
    for chats in (cat.PERSONAL_MODELS, cat.TEAM_MODELS):
        assert not set(media).intersection(chats)
        assert not {'deepseek-v3.2', 'deepseek-v4-flash'}.intersection(chats)
