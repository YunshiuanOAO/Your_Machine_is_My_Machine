# ADR-02: Layered Runtime Configuration

Date: 2026-06-03

Status: Accepted

## Context

The current package has several runtime settings:

- model/provider settings;
- report and knowledge-base paths;
- retry and wall-clock limits;
- command, scan, and web-scan timeouts;
- RAG retrieval limits such as top-k and snippet budgets;
- observability toggles for local JSONL artifacts and optional LangSmith Cloud tracing;
- allowed tool names;
- environment-specific behavior for local development, cloud testing, and HTB/Kali usage.

Keeping all of these as direct environment variables makes the system harder to reason about. It also makes cloud testing brittle because every run must recreate a long list of environment variables. On the other hand, hardcoding values in Python would make experiments slow and would force code changes for normal tuning.

Claude's review also pointed out several settings that should become explicit instead of implicit:

- a graph-level wall-clock circuit breaker, separate from command-level timeouts;
- concrete RAG budgets, for example top-k and snippet character budget;
- an explicit output artifact path contract;
- a clear v1 decision that exploit tasks run sequentially, with parallel fan-out deferred to v2.

## Decision

We will use layered configuration.

Configuration is loaded in this order, with later layers overriding earlier layers:

1. `config.yaml`: checked-in general defaults.
2. `config-<env>.yaml`: optional environment-specific override, such as `config-dev.yaml`, `config-cloud.yaml`, or `config-kali.yaml`.
3. Environment variables: final override for secrets, CI/cloud settings, and one-off experiments.

The CLI chooses the environment name with `--env`, defaulting to `dev`. The environment can also be selected with `PENTEST_ENV`.

Environment variables remain useful, but they should not be the only place configuration lives.

## Config Shape

The config file should group settings by responsibility:

```yaml
runtime:
  env: dev
  max_retries: 2
  run_timeout_seconds: 3600

model:
  provider: anthropic
  name: claude-3-7-sonnet-latest

paths:
  report_dir: reports
  knowledge_base_path: my_knowledge_base
  web_wordlist: wordlists/medium.txt

rag:
  collection_name: hacktricks_kb
  top_k: 3
  max_snippets: 6
  snippet_budget_chars: 2000

observability:
  langsmith_tracing: false
  langsmith_project: pentestagent-dev

tools:
  allowed:
    - rustscan
    - dirsearch
    - whatweb
    - searchsploit
    - msfconsole
    - curl

timeouts:
  command_seconds: 300
  scan_seconds: 300
  web_scan_seconds: 180

execution:
  auto_approve: false
  allow_interactive: false
  exploit_dispatch: sequential
```

Environment-specific override example:

```yaml
# config-cloud.yaml
runtime:
  run_timeout_seconds: 1800

execution:
  auto_approve: false

timeouts:
  scan_seconds: 600
```

Environment variables use the existing `PENTEST_` prefix and override leaf values:

```text
PENTEST_ENV=cloud
PENTEST_MODEL_NAME=claude-3-7-sonnet-latest
PENTEST_KNOWLEDGE_BASE_PATH=/mnt/data/my_knowledge_base
PENTEST_RAG_TOP_K=3
PENTEST_RAG_SNIPPET_BUDGET_CHARS=2000
PENTEST_RUN_TIMEOUT_SECONDS=1800
PENTEST_AUTO_APPROVE=false
LANGSMITH_TRACING=false
LANGSMITH_PROJECT=pentestagent-cloud
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
```

Secrets stay in environment variables and must not be written to YAML:

```text
ANTHROPIC_API_KEY=...
LANGSMITH_API_KEY=...
```

## Knowledge Base And Preprocessing Boundary

`paths.knowledge_base_path` points to an already-built Chroma persistent store. The agent treats it as a read-only runtime input: `services/rag.py` opens the store, queries the configured collection, and adds bounded snippets to decision prompts.

The runtime configuration does not describe crawler jobs, crawl targets, chunking rules, embedding batch sizes, or vectorizer output locations. Those are preprocessing concerns. The current `crawled-data/tmp/` files are development tooling and intermediate artifacts for building or experimenting with knowledge-base content; they are not loaded by `Settings`, not checked by preflight except indirectly through the final Chroma store, and not invoked during `pentestagent.main`.

There is no separate application database in v1. Chroma's internal SQLite file is an implementation detail of the knowledge base, and reports/state remain filesystem artifacts under `reports/`.

## Runtime Rules

- `run_timeout_seconds` is a graph-level circuit breaker. If the total run exceeds this limit, the graph routes to a blocked/final-report path.
- `timeouts.command_seconds` applies to one command execution.
- `timeouts.scan_seconds` applies to RustScan port-discovery steps.
- `timeouts.web_scan_seconds` applies to Dirsearch/WhatWeb web steps.
- `rag.top_k` and `rag.snippet_budget_chars` are hard context-budget controls. RAG should not silently expand prompt size.
- `observability.langsmith_tracing` defaults to `false`. LangSmith Cloud tracing is opt-in and requires `LANGSMITH_API_KEY` in the environment.
- `execution.exploit_dispatch` is `sequential` for v1. Parallel fan-out is a v2 change.
- `execution.allow_interactive` remains `false` for v1. Interactive tools require a future TTY/session manager.

## Current v1 Workflow Budgets

The graph runs in this order:

```text
recon_agent -> decision_coordinator -> exploit_agent -> approval -> command_executor -> exploit_assessor -> aggregator -> decision_coordinator/report
```

`execution.exploit_dispatch: sequential` means only one pending `ExploitTask` and one proposed command are active at a time. The current base config allows at most `runtime.max_tasks: 3` exploit tasks from the decision coordinator. `config-kali.yaml` does not override this, so Kali/HTB runs also use a maximum of three exploit tasks unless `PENTEST_MAX_TASKS` overrides it.

`runtime.max_retries` is a global retry-cycle budget for the whole run, not a per-subagent counter. The aggregator increments `retry_count` only when the latest `ExploitResult.status` is `retry`. A `failed` or `blocked` result makes that task terminal; a `success` result ends the run with a report; exhausting `max_retries` also routes to the final report.

The new spawnable-agent schema adds `AgentBudget.max_steps` and `AgentBudget.timeout_seconds` for future breadth-research and exploit worker loops. Those fields describe one worker task's local budget. They do not change the wired v1 graph yet, where `max_retries` remains global and `command_seconds` caps each executed command.

Effective default budgets:

- `config.yaml` dev/default: `max_tasks: 3`, `max_retries: 2`, `run_timeout_seconds: 3600`, `command_seconds: 300`, `scan_seconds: 300`, `web_scan_seconds: 180`.
- `config-kali.yaml`: `max_tasks: 3` inherited, `max_retries: 4`, `run_timeout_seconds: 3600`, `command_seconds: 300`, `scan_seconds: 600`, `web_scan_seconds: 300`.

For exploit-agent commands, the executor uses `min(CommandProposal.timeout_seconds, timeouts.command_seconds)`. The prompt default is `timeout_seconds: 300`, and the current command cap is also 300 seconds. Recon scans use the separate scan and web-scan timeout settings.

## CVE And RAG Selection

The agent does not run a separate CVE database sync or crawler during target testing. The decision coordinator builds Chroma queries from the normalized recon report:

- `vulnerability in <service display name>`;
- `<service_name> enumeration exploitation checklist`;
- SPIP-specific Metasploit/public-CVE queries when SPIP is detected;
- limited history queries after prior command output suggests credentials, root, or Meterpreter.

Chroma retrieval uses `rag.top_k` per query, then deduplicates snippets and stops at `rag.max_snippets`. The current default is `top_k: 3`, `max_snippets: 6`, and `snippet_budget_chars: 2000`.

The `ExploitTask.cve_id` field is optional. If the LLM sees a version-matched public vulnerability in recon facts or RAG snippets, it may set `cve_id` to `CVE-YYYY-NNNN`; the deterministic fallback tasks set `cve_id: null` and use a service-level investigation hypothesis.

## LangSmith Cloud Observability

Local observability remains the authoritative audit trail: every run writes `events.jsonl`, `recon_report.json`, command stdout/stderr excerpts, and final reports under `reports/<run_id>/`.

LangSmith Cloud is additive. When `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` are exported, `pentestagent.main` wraps the graph invocation in a LangSmith tracing context and passes run metadata such as target IP, run ID, environment, model, retry budget, and task budget. The Anthropic client is wrapped with LangSmith's Anthropic wrapper so model calls appear as child spans when tracing is enabled.

Do not put `LANGSMITH_API_KEY` in YAML. `LANGSMITH_PROJECT` and `LANGSMITH_ENDPOINT` are non-secret environment/config knobs; `LANGSMITH_ENDPOINT` is needed only for non-default LangSmith regions. Because traces may contain prompts, recon details, proposed commands, and selected command output excerpts, operators should leave tracing disabled for sensitive targets or data that should not leave the local lab.

## Implementation Notes

- Keep a single `Settings` object as the typed runtime config.
- Load YAML first, then apply environment-variable overrides.
- Do not use raw nested dictionaries throughout the app; normalize into `Settings`.
- Chroma is a normal runtime dependency because the default decision workflow can query the local knowledge base.
- LangSmith is a normal runtime dependency because the optional cloud tracing path imports the SDK directly.
- Keep crawler and vectorizer tooling outside runtime config until there is a supported preprocessing workflow.
- Keep `.env.example` as documentation for environment-variable overrides, not as the primary config.
- Add tests for config precedence:
  - base config only;
  - base plus environment-specific YAML;
  - env vars overriding both YAML layers.

## Consequences

Positive:

- Local, cloud, and Kali/HTB runs can share one codebase with different config files.
- RAG budgets and top-k become explicit and testable.
- Timeouts are easier to reason about because run-level and command-level limits are separate.
- Fewer long command lines and fewer fragile `.env` files.

Negative:

- Adds a small config loader.
- Adds YAML as a project dependency.
- Requires discipline to avoid adding duplicate env-only settings.

## Guardrails

- Do not store secrets in YAML config files.
- Do not let environment-specific config files override safety defaults silently for dangerous behavior such as interactive execution.
- Keep `config.yaml` conservative; aggressive scan/risk settings belong in explicit environment overrides.
- Every new setting should have a clear owner and a testable behavior.
