import sys
import types

from pentestagent.config import Settings
from pentestagent.services.llm import ClaudeJSONClient


def test_openai_compatible_client_uses_base_url_and_key(monkeypatch):
    captured = {}

    class FakeMessage:
        content = '{"ok": true}'

    class FakeChoice:
        message = FakeMessage()

    class FakeCompletions:
        def create(self, **kwargs):
            captured["completion_kwargs"] = kwargs
            return types.SimpleNamespace(choices=[FakeChoice()])

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = FakeChat()

    fake_module = types.SimpleNamespace(OpenAI=FakeOpenAI)
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    settings = Settings(
        model_provider="openai",
        model="gpt-test",
        openai_api_key="test-key",
        openai_base_url="https://api.yunshiuan.com/",
    )

    result = ClaudeJSONClient(settings).complete_json("system", {"hello": "world"})

    assert result == {"ok": True}
    assert captured["client_kwargs"] == {
        "api_key": "test-key",
        "base_url": "https://api.yunshiuan.com/",
    }
    assert captured["completion_kwargs"]["model"] == "gpt-test"
    assert captured["completion_kwargs"]["messages"][0] == {"role": "system", "content": "system"}
