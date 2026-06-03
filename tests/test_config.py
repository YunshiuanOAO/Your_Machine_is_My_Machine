from pentestagent.config import Settings


def test_settings_loads_base_config(tmp_path):
    (tmp_path / "config.yaml").write_text(
        """
runtime:
  max_retries: 4
  run_timeout_seconds: 120
model:
  name: claude-test
paths:
  knowledge_base_path: kb
rag:
  collection_name: test_collection
  top_k: 5
  max_snippets: 7
  snippet_budget_chars: 1234
timeouts:
  command_seconds: 11
execution:
  auto_approve: false
tools:
  allowed: [nmap, curl]
""",
        encoding="utf-8",
    )

    settings = Settings.load(project_root=tmp_path, environ={})

    assert settings.env == "dev"
    assert settings.model == "claude-test"
    assert settings.knowledge_base_path == "kb"
    assert settings.collection_name == "test_collection"
    assert settings.max_retries == 4
    assert settings.run_timeout_seconds == 120
    assert settings.command_timeout == 11
    assert settings.rag_top_k == 5
    assert settings.max_rag_snippets == 7
    assert settings.rag_snippet_budget_chars == 1234
    assert settings.langsmith_tracing is False
    assert settings.langsmith_project == "pentestagent-dev"
    assert settings.allowed_tools == ("nmap", "curl")


def test_env_specific_config_overrides_base(tmp_path):
    (tmp_path / "config.yaml").write_text(
        """
runtime:
  max_retries: 2
timeouts:
  scan_seconds: 100
execution:
  exploit_dispatch: sequential
""",
        encoding="utf-8",
    )
    (tmp_path / "config-cloud.yaml").write_text(
        """
runtime:
  max_retries: 9
timeouts:
  scan_seconds: 600
execution:
  exploit_dispatch: sequential
""",
        encoding="utf-8",
    )

    settings = Settings.load(env="cloud", project_root=tmp_path, environ={})

    assert settings.env == "cloud"
    assert settings.max_retries == 9
    assert settings.scan_timeout == 600
    assert settings.exploit_dispatch == "sequential"


def test_environment_variables_override_yaml_layers(tmp_path):
    (tmp_path / "config.yaml").write_text(
        """
runtime:
  max_retries: 2
rag:
  top_k: 3
  snippet_budget_chars: 2000
execution:
  auto_approve: false
tools:
  allowed: [nmap]
""",
        encoding="utf-8",
    )

    settings = Settings.load(
        project_root=tmp_path,
        environ={
            "PENTEST_ENV": "cloud",
            "PENTEST_MAX_RETRIES": "6",
            "PENTEST_RAG_TOP_K": "8",
            "PENTEST_RAG_SNIPPET_BUDGET_CHARS": "777",
            "PENTEST_AUTO_APPROVE": "true",
            "PENTEST_ALLOWED_TOOLS": "nmap,curl",
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_API_KEY": "lsv2_test",
            "LANGSMITH_PROJECT": "pentestagent-test",
            "LANGSMITH_ENDPOINT": "https://eu.api.smith.langchain.com",
        },
    )

    assert settings.env == "cloud"
    assert settings.max_retries == 6
    assert settings.rag_top_k == 8
    assert settings.rag_snippet_budget_chars == 777
    assert settings.auto_approve is True
    assert settings.allowed_tools == ("nmap", "curl")
    assert settings.langsmith_tracing is True
    assert settings.langsmith_api_key == "lsv2_test"
    assert settings.langsmith_project == "pentestagent-test"
    assert settings.langsmith_endpoint == "https://eu.api.smith.langchain.com"
