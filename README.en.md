<p align="center">
  <img src="docs/assets/logo.png" alt="Your_Machine_is_My_Machine logo" width="860">
</p>

<p align="center">
  <a href="README.md">中文</a> | <strong>English</strong>
</p>

<p align="center">
  <a href="https://youtu.be/w-S8ucXFpPs">
    <img src="https://img.youtube.com/vi/w-S8ucXFpPs/maxresdefault.jpg" alt="Your_Machine_is_My_Machine demo video" width="860">
  </a>
</p>

<p align="center">
  <a href="https://youtu.be/w-S8ucXFpPs"><strong>Watch the Demo Video</strong></a>
</p>

---

# Your_Machine_is_My_Machine

**Your_Machine_is_My_Machine** is a coordinator-specialist penetration-testing agent for authorized lab targets. It performs recon, lets a decision coordinator create parallel solver tasks, and then writes the successful path, shell handoff, final report, and reusable success skill.

```text
Recon Agent -> Decision Coordinator -> Solver Fan-Out -> Agent Monitor -> Shell Handoff -> Report
```

LLM / Codex solvers produce structured tasks, evidence, and observable reasoning. Commands are still executed locally, and full artifacts are written to the run directory.

## Demo

Click the image below to watch the demo video:

<p align="center">
  <a href="https://youtu.be/w-S8ucXFpPs">
    <img src="https://img.youtube.com/vi/w-S8ucXFpPs/maxresdefault.jpg" alt="Your_Machine_is_My_Machine demo video" width="860">
  </a>
</p>

## Features

- Recon and service fingerprinting.
- Decision coordinator for next-step exploit planning.
- Codex SDK exploit fan-out with multiple solver agents.
- Web dashboard:
  - Execution Tree
  - Agent Workspaces monitor wall
  - token usage charts
  - solver detail modal
  - shell access / attach command
  - final report
- Final report generation when shell access is obtained or the run is exhausted.
- Successful chains generate `success_skill/SKILL.md` for future reuse.
- Anthropic and OpenAI-compatible providers.
- Kali / HTB VPN workflow.

## Requirements

- Python managed with `uv`
- Node.js / npm for Codex SDK workers
- LLM API key:
  - Anthropic API key, or
  - OpenAI-compatible API key
- Optional LangSmith API key for tracing
- Chroma-backed local knowledge base dependencies
- Recommended Kali / HTB tools:
  - `rustscan`
  - `nmap`
  - `dirsearch`
  - `whatweb`
  - `searchsploit`
  - `msfconsole`
  - `curl`

## Install

Install Python dependencies:

```bash
uv sync
```

For development and tests:

```bash
uv sync --group dev
```

Install Node worker dependencies:

```bash
npm install
```

## API Key Setup

### Anthropic

```bash
export ANTHROPIC_API_KEY="..."
```

Or use the helper so pasted secrets are hidden and not written to shell history:

```bash
source scripts/config_secrets.sh
```

For Kali / HTB:

```bash
ENV=kali source scripts/config_secrets.sh
```

### OpenAI-Compatible Provider

Example Yunshiuan endpoint:

```bash
export PENTEST_MODEL_PROVIDER=openai
export PENTEST_MODEL_NAME=gpt-4.1-mini
export OPENAI_BASE_URL="https://api.yunshiuan.com/"
export OPENAI_API_KEY="..."
uv run python -m pentestagent.main -t <TARGET_IP> --env openai
```

You can also create a local `.env` based on `.env.example`. Do not commit real API keys.

### LangSmith Tracing

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT=pentestagent-dev
```

LangSmith traces may include prompts, recon summaries, command proposals, and selected command output excerpts. Keep tracing disabled for data you do not want uploaded.

## Configuration

Runtime configuration is layered:

1. `config.yaml`
2. `config-<env>.yaml`
3. environment variables

Kali / HTB overrides live in:

```text
config-kali.yaml
```

Common env values:

```bash
export PENTEST_EXPLOIT_DISPATCH=codex_parallel
export PENTEST_DECISION_BACKEND=codex
export PENTEST_CODEX_DECISION_TIMEOUT_SECONDS=60
export PENTEST_CODEX_DECISION_WORKER_COMMAND="node scripts/codex_decision_worker.mjs"
export PENTEST_CODEX_WORKER_COMMAND="node scripts/codex_exploit_worker.mjs"
```

## VPN / HTB Setup

VPN setup is intentionally outside Python. Put `.ovpn` profiles under the gitignored `vpn/` directory:

```bash
./scripts/config_vpn.sh vpn/machines_us-3.ovpn tun0
source .pentestagent-vpn.env
```

The Python agent only receives the target IP. Linux routing through the VPN makes the target reachable.

## Run

Standard Kali / HTB run:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

Auto-approve mode:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --auto-approve
```

Disable dashboard:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --no-ui
```

Useful UI flags:

```bash
--ui-host 0.0.0.0
--ui-port 8765
--no-ui-browser
--no-ui-hold
```

## Dashboard

The CLI starts a dashboard by default:

```text
Dashboard: http://127.0.0.1:8765
```

The dashboard shows:

- run state and run directory
- token usage charts
- Execution Tree
- Solver agent monitor wall
- agent detail modal
- shell access / attach command
- final report

The dashboard shows observable artifacts, not hidden model chain-of-thought.

## Codex SDK Fan-Out

Enable parallel solver mode:

```bash
export PENTEST_EXPLOIT_DISPATCH=codex_parallel
export PENTEST_DECISION_BACKEND=codex
export PENTEST_CODEX_DECISION_WORKER_COMMAND="node scripts/codex_decision_worker.mjs"
export PENTEST_CODEX_WORKER_COMMAND="node scripts/codex_exploit_worker.mjs"
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

Behavior:

- The decision coordinator creates scoped solver tasks from recon, RAG, and previous results.
- All generated worker tasks are dispatched.
- Workers return success / failed / retry / blocked.
- If one branch obtains an attachable shell, sibling branches are cancelled.
- The final report records shell handoff details.
- Successful runs generate `success_skill/SKILL.md`.

Worker diagnostics:

```text
reports/<run>/codex_decision/payload.json
reports/<run>/codex_decision/stdout.txt
reports/<run>/codex_decision/stderr.txt
reports/<run>/agent_workers/
reports/<run>/agent_reports/
```

## Test

Full test suite:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

Knowledge base only:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/test_knowledge_base.py -q
```

Deterministic fallback without LLM calls:

```bash
uv run python -m pentestagent.main -t 10.10.10.10 --env dev --skip-scan --no-llm
```

Preflight:

```bash
./scripts/preflight.sh
```

## Existing Scan Artifacts

```bash
uv run python -m pentestagent.main \
  -t <TARGET_IP> \
  --env kali \
  --rustscan-file path/to/rustscan_raw.txt \
  --dirsearch-file path/to/dirsearch_output.json
```

## Outputs

Every run writes:

```text
reports/<run_id>/
```

Common outputs:

```text
events.jsonl
recon_report.json
final_report.json
final_report.md
agent_workers/
agent_reports/
success_skill/SKILL.md
```

If shell access is available, the terminal prints:

```text
Shell access: available
Shell attach (...): <attach command>
```

## Safety

Use this project only against targets you are authorized to test, such as labs, CTFs, HTB machines, internal systems, or research environments. Do not scan, exploit, or test credentials against unauthorized targets.
