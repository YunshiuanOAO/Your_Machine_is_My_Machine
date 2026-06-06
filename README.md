# pentestagent

A coordinator-specialist pentest agent for authorized lab targets. The v1 workflow keeps command execution local and explicit:

```text
Recon Agent -> Decision Coordinator -> Exploit Agent -> Approval -> Executor -> Report
```

LLM agents propose structured commands, but only the local executor validates and runs them.

## Requirements

- Python managed with `uv`
- An Anthropic API key for LLM-backed runs
- Optional LangSmith API key for cloud tracing
- Chroma-backed local knowledge base dependencies
- External tools for live Kali scans:
  - `rustscan`
  - `nmap`
  - `dirsearch`
  - `whatweb`
  - optional proposal tools: `searchsploit`, `msfconsole`, `curl`

## Install

```bash
uv sync
```

For full local/preflight runs, include dev tools:

```bash
uv sync --group dev
```

Set your API key:

```bash
export ANTHROPIC_API_KEY="..."
```

Or use the prompt helper so pasted secrets are hidden and not written to shell history:

```bash
source scripts/config_secrets.sh
```

For Kali/HTB runs, source it with the Kali environment so it prints the VPN setup reminder:

```bash
ENV=kali source scripts/config_secrets.sh
```

## OpenAI-Compatible Provider

The agent can use an OpenAI-compatible Chat Completions endpoint instead of Anthropic.

For the Yunshiuan endpoint:

```bash
export PENTEST_MODEL_PROVIDER=openai
export PENTEST_MODEL_NAME=gpt-4.1-mini
export OPENAI_BASE_URL="https://api.yunshiuan.com/"
export OPENAI_API_KEY="..."
uv run python -m pentestagent.main -t <TARGET_IP> --env openai
```

Keep real API keys out of git. For GitHub Actions or Kali deploys, store the key as a GitHub Secret or on the Kali host environment as `OPENAI_API_KEY`.

You can also set these in an untracked local `.env` file based on `.env.example`, then export them before running the agent.

Optional LangSmith Cloud tracing:

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT=pentestagent-dev
```

LangSmith traces can include prompts, recon summaries, command proposals, and selected command output excerpts. Keep tracing disabled for data you do not want uploaded to LangSmith Cloud.

The default knowledge base path is configured as `PENTEST_KNOWLEDGE_BASE_PATH` and currently points to `my_knowledge_base`.

## Configuration

Runtime configuration is layered:

1. `config.yaml`
2. `config-<env>.yaml`, selected by `--env <env>` or `PENTEST_ENV`
3. environment variables

Kali/HTB-specific overrides live in:

```text
config-kali.yaml
```

The Kali config uses longer scan timeouts, keeps human approval enabled, and keeps exploit dispatch sequential for v1.

VPN setup is intentionally outside Python. Put local VPN profiles under the gitignored `vpn/` directory, then use the shell helper before running the agent:

```bash
./scripts/config_vpn.sh vpn/machines_us-3.ovpn tun0
source .pentestagent-vpn.env
```

The agent itself only receives the target IP. Linux routing through the VPN makes the target reachable.

## Test Locally

Run the unit suite:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

Validate only the knowledge base:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/test_knowledge_base.py -q
```

Run without Claude calls using deterministic fallbacks:

```bash
uv run python -m pentestagent.main -t 10.10.10.10 --env dev --skip-scan --no-llm
```

## 3D Run Dashboard

The CLI starts a local dashboard by default for interactive runs. It shows the current stage, agent task branches, observable prompts/payloads/responses, command proposals, command output artifacts, and the final report.

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

The CLI prints the dashboard URL:

```text
Dashboard: http://127.0.0.1:8765
```

Useful flags:

```bash
--no-ui            # disable the dashboard
--ui-host 0.0.0.0  # bind outside localhost, only for trusted lab networks
--ui-port 8765
--no-ui-browser   # do not try to open a browser
--no-ui-hold      # exit immediately after completion instead of keeping the dashboard alive
```

The dashboard intentionally shows complete observable artifacts, not hidden model chain-of-thought. Visible reasoning includes model prompts, payloads, structured responses, command proposal reasoning, execution results, and reports.

## Codex SDK Exploit Fan-Out

The decision coordinator can fan out multiple scoped exploit agents through the Codex SDK. Each branch returns an `AgentRunResult` report whether it succeeds, fails, retries, or is blocked. If one branch succeeds, the dispatcher cancels still-running sibling branches and the final report is produced.

Install the Node SDK worker dependencies:

```bash
npm install
```

Run in fan-out mode:

```bash
export PENTEST_EXPLOIT_DISPATCH=codex_parallel
export PENTEST_DECISION_BACKEND=codex
export PENTEST_CODEX_DECISION_TIMEOUT_SECONDS=60
export PENTEST_CODEX_DECISION_WORKER_COMMAND="node scripts/codex_decision_worker.mjs"
export PENTEST_CODEX_WORKER_COMMAND="node scripts/codex_exploit_worker.mjs"
export PENTEST_MAX_PARALLEL_EXPLOIT_AGENTS=3
export PENTEST_DECISION_MAX_ROUNDS=3
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

Decision behavior in this mode:

- Generate several scoped exploit worker tasks from recon, RAG, and previous branch reports.
- Dispatch up to `PENTEST_MAX_PARALLEL_EXPLOIT_AGENTS` Codex SDK workers.
- Require every worker to return a complete exploit report, including failed and blocked attempts.
- Re-run decision after failed rounds, using the previous reports as context.
- Stop when any branch succeeds, when no useful branch remains, or when `PENTEST_DECISION_MAX_ROUNDS` is reached.

Codex decision worker diagnostics are written to `reports/<run>/codex_decision/payload.json`, `stdout.txt`, and `stderr.txt`. If Codex is unavailable, times out, or reports a worker failure, the coordinator falls back to the regular LLM or heuristic task builder.

Both Codex SDK workers run with `workspace-write` sandbox mode and `sandbox_workspace_write.network_access=true`, so scoped worker commands can reach the lab target network. The host running PentestAgent still needs real routing to the target, such as an active VPN interface for HTB.

## Kali/HTB Test Flow

Use Kali or a Kali-like VM for live HTB testing because the scanner flow depends on pentest tools and VPN/network routing.

1. Clone or copy this project onto the Kali VM.

2. Install Python dependencies:

```bash
uv sync --group dev
```

3. Confirm your secret is available:

```bash
ENV=kali source scripts/config_secrets.sh
```

4. Put your `.ovpn` profile under `vpn/`, then start/check the HTB VPN:

```bash
./scripts/config_vpn.sh vpn/machines_us-3.ovpn tun0
source .pentestagent-vpn.env
```

The shell script owns VPN setup. Python does not configure VPN, routes, interfaces, or LHOST.

5. Run the executable preflight:

```bash
./scripts/preflight.sh
```

The preflight checks:

- `uv`
- Python dependencies
- Chroma/runtime dependencies
- `rustscan`, `nmap`, `dirsearch`, `whatweb`
- optional proposal tools such as `searchsploit`, `msfconsole`, and `curl`
- `config.yaml` and `config-kali.yaml`
- shell-exported VPN interface, if running Kali/HTB
- configured wordlist path
- Chroma knowledge base
- `ANTHROPIC_API_KEY`
- LangSmith env wiring, if `LANGSMITH_TRACING=true`
- the pytest suite

6. First live run, without auto-approval:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

Review each proposed command before approving it. After you trust the behavior in your lab, you can opt into automatic approval:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --auto-approve
```

See `docs/ADR-05-CLI Runbook and Auto-Approve Mode.md` for the full CLI command catalog and approval-mode rules.

## Using Existing Scan Artifacts

You can skip live scanning and load existing artifacts:

```bash
uv run python -m pentestagent.main \
  -t <TARGET_IP> \
  --env kali \
  --rustscan-file path/to/rustscan_raw.txt \
  --dirsearch-file path/to/dirsearch_output.json
```

If you pass artifact files, the agent references those paths in `recon_report.json`; it does not create a new `scan/` directory.

## Output

Each run writes to:

```text
reports/<run_id>/
```

Always expected for normal completion:

```text
events.jsonl
recon_report.json
final_report.json
final_report.md
```

For a full scanner-backed run, `scan/` is created:

```text
scan/
├── rustscan_raw.txt
├── nmap_service.xml
├── dirsearch_output.json
└── whatweb_output.json
```

When commands are proposed and executed or blocked, `commands/` is created:

```text
commands/
├── <command_id>.stdout.txt
└── <command_id>.stderr.txt
```

The command id is a UUID. Its task mapping and command metadata are recorded in `events.jsonl` and `final_report.json`.

If `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` are exported, the LangGraph run and Anthropic model calls are also traced to the configured LangSmith project. Local artifact files are still written either way.

## Useful Commands

Run with Kali config:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

Run without scanning:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --skip-scan
```

Run without LLM calls:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --no-llm
```

Override retry budget:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --max-retries 6
```

## VPN Profiles

Use `vpn/` for local `.ovpn` files:

```text
vpn/
└── machines_us-3.ovpn
```

The directory is kept in the repo with `vpn/.gitkeep`, but its contents are ignored. This is the future-friendly path for an uploaded VPN profile plus target IP:

```bash
./scripts/config_vpn.sh vpn/<uploaded>.ovpn tun0
source .pentestagent-vpn.env
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

## Troubleshooting

- No `scan/` directory: the run used `--skip-scan`, supplied artifact files, or ended before the scanner flow started.
- No `commands/` directory: no exploit task produced an executable command, or the run ended after recon/decision.
- `Tool not found on PATH`: install the missing Kali tool and re-run `./scripts/preflight.sh`.
- VPN interface missing: run `./scripts/config_vpn.sh vpn/<profile>.ovpn tun0`, then `source .pentestagent-vpn.env`.
- Chroma import failure: run `uv sync`.
- Knowledge-base failure: confirm `my_knowledge_base/` exists and contains the expected Chroma collection.
- LangSmith warning: export `LANGSMITH_API_KEY` only when `LANGSMITH_TRACING=true`; otherwise cloud tracing is intentionally disabled.
- Terminal stopped showing typed characters after an interrupted hidden prompt or approval prompt: run `stty sane`.

Only run this against systems where you have explicit authorization.
