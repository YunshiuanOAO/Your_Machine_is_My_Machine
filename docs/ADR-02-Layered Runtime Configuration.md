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

tools:
  allowed:
    - nmap
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
```

Secrets stay in environment variables and must not be written to YAML:

```text
ANTHROPIC_API_KEY=...
```

## Knowledge Base And Preprocessing Boundary

`paths.knowledge_base_path` points to an already-built Chroma persistent store. The agent treats it as a read-only runtime input: `services/rag.py` opens the store, queries the configured collection, and adds bounded snippets to decision prompts.

The runtime configuration does not describe crawler jobs, crawl targets, chunking rules, embedding batch sizes, or vectorizer output locations. Those are preprocessing concerns. The current `crawled-data/tmp/` files are development tooling and intermediate artifacts for building or experimenting with knowledge-base content; they are not loaded by `Settings`, not checked by preflight except indirectly through the final Chroma store, and not invoked during `pentestagent.main`.

There is no separate application database in v1. Chroma's internal SQLite file is an implementation detail of the knowledge base, and reports/state remain filesystem artifacts under `reports/`.

## Runtime Rules

- `run_timeout_seconds` is a graph-level circuit breaker. If the total run exceeds this limit, the graph routes to a blocked/final-report path.
- `timeouts.command_seconds` applies to one command execution.
- `timeouts.scan_seconds` applies to RustScan/Nmap scan steps.
- `timeouts.web_scan_seconds` applies to Dirsearch/WhatWeb web steps.
- `rag.top_k` and `rag.snippet_budget_chars` are hard context-budget controls. RAG should not silently expand prompt size.
- `execution.exploit_dispatch` is `sequential` for v1. Parallel fan-out is a v2 change.
- `execution.allow_interactive` remains `false` for v1. Interactive tools require a future TTY/session manager.

## Implementation Notes

- Keep a single `Settings` object as the typed runtime config.
- Load YAML first, then apply environment-variable overrides.
- Do not use raw nested dictionaries throughout the app; normalize into `Settings`.
- Chroma is a normal runtime dependency because the default decision workflow can query the local knowledge base.
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
