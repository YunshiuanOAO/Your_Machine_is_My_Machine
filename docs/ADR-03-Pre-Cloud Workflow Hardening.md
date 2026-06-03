# ADR-03: Pre-Cloud Workflow Hardening

Date: 2026-06-03

Status: Accepted

## Context

Before testing the agent on cloud or Kali infrastructure, we reviewed the current v1 workflow for correctness and operational clarity. Five issues were identified:

- retry exhaustion routing was misleading because both branches returned to the decision node;
- test coverage needed to explicitly protect high-risk behavior such as command validation and retry routing;
- Dirsearch parsing depended on console output instead of Dirsearch's native JSON output;
- the default Claude model should be configurable and should use a stronger current Sonnet default where possible;
- Metasploit/searchsploit are allowlisted command tools, but full Metasploit orchestration is not implemented.

## Decision

We will harden the v1 workflow without expanding scope into interactive exploitation or full Metasploit automation.

The fixes are:

- `route_after_aggregate` routes to `report` when `retry_count >= max_retries`.
- Dirsearch is invoked with `--format=json -o <path>`.
- Dirsearch parsing accepts both native object output (`{"results": [...]}`) and the normalized list format used by the report pipeline.
- Default model config is updated to `claude-sonnet-4-6`, while remaining overrideable through YAML and environment variables.
- Test coverage explicitly includes command allowlist rejection, shell-metacharacter blocking, retry exhaustion routing, Dirsearch native JSON parsing, and config precedence.

We will also add a Kali/HTB preflight workflow before cloud or VM testing:

- `config-kali.yaml` contains Kali-specific runtime overrides.
- `scripts/preflight.sh` performs executable checks instead of relying on a static checklist.
- `scripts/msfinstall.sh` preserves the existing Metasploit installer helper under the `scripts/` directory.

## Scope Boundaries

Metasploit and searchsploit remain allowlisted tools that an exploit agent may propose through `CommandProposal`. They are not orchestrated by `scan_runner.py`, and v1 does not automate Metasploit module selection, payload setup, session handling, or post-exploitation.

Interactive execution remains disabled in v1. A future ADR should define a TTY/session manager before enabling `requires_interactive=True`.

The preflight script checks whether Metasploit is available but does not install or configure it automatically. If Metasploit is missing on Kali, the operator may run `scripts/msfinstall.sh` manually with appropriate privileges.

Knowledge-base validation means validating the already-built Chroma store configured by `paths.knowledge_base_path`. Preflight must not crawl websites, rebuild chunks, generate embeddings, or mutate the knowledge base as part of target testing. The crawler/vectorizer files under `crawled-data/tmp/` are development preprocessing tools only.

## Kali/HTB Preflight

Before running against an HTB target on Kali:

```text
uv sync --group dev
export ANTHROPIC_API_KEY=...
./scripts/config_vpn.sh vpn/machines_us-3.ovpn tun0
source .pentestagent-vpn.env
./scripts/preflight.sh
uv run python -m pentestagent.main -t <TARGET> --env kali
```

First live runs should not use `--auto-approve`; every generated `CommandProposal` should be reviewed by the operator.

`scripts/preflight.sh` must check:

- `uv` is installed;
- core Python dependencies import;
- runtime Chroma and dev dependencies import after `uv sync --group dev`;
- hard-required scan tools are on `PATH`: `rustscan`, `nmap`, `dirsearch`, `whatweb`;
- allowlisted but optional proposal tools are present or warned: `searchsploit`, `msfconsole`, `curl`;
- `config.yaml` and `config-kali.yaml` are present;
- the configured wordlist path exists;
- the shell-exported VPN interface exists for Kali/HTB runs;
- the configured knowledge base validates through `tests/test_knowledge_base.py`;
- crawler/preprocessing scripts are not required for runtime preflight;
- `ANTHROPIC_API_KEY` is set, unless the run will use `--no-llm`;
- the full pytest suite passes.

The script exits non-zero on hard failures and prints the exact `uv run python -m pentestagent.main ... --env kali` command to start the agent.

## Consequences

Positive:

- Retry behavior now matches the ADR-01 workflow: exhausted retries produce a final report instead of another decision pass.
- Web findings are less brittle because Dirsearch JSON is the primary input.
- The cloud/Kali test path has clearer failure modes.
- The stronger model default can improve task and command proposals without code changes.

Negative:

- The `claude-sonnet-4-6` model name may need to be overridden in environments that require a fully versioned Anthropic API model ID.
- Dirsearch installations with incompatible CLI flags will fall back to an empty or console-parsed result, so Kali validation is still required.
- Full Metasploit automation remains deferred.

## Validation

The workflow must pass the unit suite before cloud testing:

```text
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

The expected coverage includes:

- config layering and environment overrides;
- knowledge-base path and collection checks;
- command executor guardrails;
- retry-exhaustion routing;
- RAG snippet budgeting;
- Dirsearch native JSON parsing.

Kali-specific validation also includes:

```text
bash -n scripts/config_vpn.sh
bash -n scripts/preflight.sh
bash -n scripts/msfinstall.sh
```
