import os

from pentestagent.config import Settings
from pentestagent.observability.langsmith import langsmith_enabled, langsmith_run_config


def test_langsmith_disabled_without_key():
    settings = Settings(langsmith_tracing=True, langsmith_api_key=None)

    assert langsmith_enabled(settings) is False
    assert langsmith_run_config(settings, "10.10.10.10", "run_1") is None


def test_langsmith_run_config_includes_metadata(monkeypatch):
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    settings = Settings(
        env="kali",
        model="claude-test",
        langsmith_tracing=True,
        langsmith_api_key="lsv2_test",
        langsmith_project="pentestagent-kali",
        max_retries=4,
    )

    config = langsmith_run_config(settings, "10.10.10.10", "run_1")

    assert config is not None
    assert config["run_name"] == "pentestagent"
    assert config["tags"] == ["pentestagent", "env:kali"]
    assert config["metadata"]["target_ip"] == "10.10.10.10"
    assert config["metadata"]["run_id"] == "run_1"
    assert config["metadata"]["max_retries"] == 4
    assert "max_tasks" not in config["metadata"]
    assert os.environ["LANGSMITH_API_KEY"] == "lsv2_test"
