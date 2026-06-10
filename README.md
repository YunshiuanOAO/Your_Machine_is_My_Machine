<p align="center">
  <img src="docs/assets/ymimm-logo.svg" alt="Your Machine is My Machine logo" width="860">
</p>

<p align="center">
  <a href="#中文">中文</a> | <a href="#english">English</a>
</p>

<p align="center">
  <strong>Demo video coming soon.</strong>
</p>

---

# 中文

## 專案介紹

**Your Machine is My Machine** 是一個針對授權實驗室目標設計的 coordinator-specialist 滲透測試代理系統。它會先做 recon，再由 decision coordinator 產生可並行的 exploit solver 任務，最後彙整成功路徑、shell handoff、報告與可重用 skill。

核心流程：

```text
Recon Agent -> Decision Coordinator -> Solver Fan-Out -> Agent Monitor -> Shell Handoff -> Report
```

LLM / Codex solver 會提出結構化任務與證據，實際命令仍由本地環境執行，並保留完整 observable artifacts。

## 主要功能

- Recon 與服務指紋辨識。
- Decision coordinator 自動產生下一步滲透任務。
- Codex SDK exploit fan-out，可同時派發多個 solver agent。
- Web dashboard：
  - Execution Tree
  - Agent Workspaces 監控牆
  - token 使用統計與圖表
  - final report
  - shell access / attach command
- 成功拿到 shell 時產生 final report。
- 成功鏈會輸出 `success_skill/SKILL.md`，方便之後重用。
- 支援 Anthropic 與 OpenAI-compatible provider。
- 支援 Kali / HTB VPN 工作流。

## Demo

Demo video will be added here later.

```text
TODO: Add demo video / GIF / asciinema link.
```

## 系統需求

- Python with `uv`
- Node.js / npm，供 Codex SDK worker 使用
- LLM API key：
  - Anthropic API key，或
  - OpenAI-compatible API key
- 可選：LangSmith API key，用於 tracing
- 本地知識庫依賴：Chroma
- Kali / HTB live scan 建議工具：
  - `rustscan`
  - `nmap`
  - `dirsearch`
  - `whatweb`
  - `searchsploit`
  - `msfconsole`
  - `curl`

## 安裝

安裝 Python dependencies：

```bash
uv sync
```

如果要跑完整測試或開發工具：

```bash
uv sync --group dev
```

安裝 Node worker dependencies：

```bash
npm install
```

## 設定 API Key

### Anthropic

```bash
export ANTHROPIC_API_KEY="..."
```

或使用 helper，避免 secret 進入 shell history：

```bash
source scripts/config_secrets.sh
```

Kali / HTB 環境：

```bash
ENV=kali source scripts/config_secrets.sh
```

### OpenAI-Compatible Provider

例如 Yunshiuan endpoint：

```bash
export PENTEST_MODEL_PROVIDER=openai
export PENTEST_MODEL_NAME=gpt-4.1-mini
export OPENAI_BASE_URL="https://api.yunshiuan.com/"
export OPENAI_API_KEY="..."
uv run python -m pentestagent.main -t <TARGET_IP> --env openai
```

也可以參考 `.env.example` 建立本地 `.env`，但不要把真實 API key commit 進 git。

### LangSmith Tracing

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT=pentestagent-dev
```

LangSmith traces 可能包含 prompt、recon summary、command proposal 與部分 command output。若資料不適合上傳，請保持 tracing 關閉。

## 設定檔

runtime 設定依序覆蓋：

1. `config.yaml`
2. `config-<env>.yaml`
3. environment variables

Kali / HTB 使用：

```text
config-kali.yaml
```

常用 env：

```bash
export PENTEST_EXPLOIT_DISPATCH=codex_parallel
export PENTEST_DECISION_BACKEND=codex
export PENTEST_CODEX_DECISION_TIMEOUT_SECONDS=60
export PENTEST_CODEX_DECISION_WORKER_COMMAND="node scripts/codex_decision_worker.mjs"
export PENTEST_CODEX_WORKER_COMMAND="node scripts/codex_exploit_worker.mjs"
```

## VPN / HTB 設定

VPN 設定不由 Python 處理。請把 `.ovpn` 放在 gitignored `vpn/` 目錄：

```bash
./scripts/config_vpn.sh vpn/machines_us-3.ovpn tun0
source .pentestagent-vpn.env
```

Python agent 只接收 target IP，實際路由由 Linux / VPN interface 負責。

## 執行

一般 Kali / HTB run：

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

自動批准命令：

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --auto-approve
```

關閉 dashboard：

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --no-ui
```

常用 UI 參數：

```bash
--ui-host 0.0.0.0
--ui-port 8765
--no-ui-browser
--no-ui-hold
```

## Dashboard

CLI 預設啟動 dashboard：

```text
Dashboard: http://127.0.0.1:8765
```

Dashboard 顯示：

- 執行狀態與 run directory
- token usage 圖表
- Execution Tree
- Solver agent 監控牆
- agent detail modal
- shell access / attach command
- final report

Dashboard 只顯示 observable artifacts，不顯示 hidden model chain-of-thought。

## Codex SDK Fan-Out

啟用並行 solver：

```bash
export PENTEST_EXPLOIT_DISPATCH=codex_parallel
export PENTEST_DECISION_BACKEND=codex
export PENTEST_CODEX_DECISION_WORKER_COMMAND="node scripts/codex_decision_worker.mjs"
export PENTEST_CODEX_WORKER_COMMAND="node scripts/codex_exploit_worker.mjs"
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

行為：

- decision coordinator 從 recon、RAG、前一輪結果產生多個 scoped solver tasks。
- 所有產生的 worker tasks 都會派發。
- worker 回傳 success / failed / retry / blocked。
- 任一 branch 取得可 attach shell 時停止其他 sibling branches。
- final report 會記錄 shell handoff。
- 成功時會產生 `success_skill/SKILL.md`。

worker diagnostic artifacts：

```text
reports/<run>/codex_decision/payload.json
reports/<run>/codex_decision/stdout.txt
reports/<run>/codex_decision/stderr.txt
reports/<run>/agent_workers/
reports/<run>/agent_reports/
```

## 測試

完整測試：

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

只測知識庫：

```bash
UV_CACHE_DIR=.uv-cache uv run pytest tests/test_knowledge_base.py -q
```

不呼叫 LLM 的 deterministic fallback：

```bash
uv run python -m pentestagent.main -t 10.10.10.10 --env dev --skip-scan --no-llm
```

preflight：

```bash
./scripts/preflight.sh
```

## 使用既有掃描 artifacts

```bash
uv run python -m pentestagent.main \
  -t <TARGET_IP> \
  --env kali \
  --rustscan-file path/to/rustscan_raw.txt \
  --dirsearch-file path/to/dirsearch_output.json
```

## 輸出

每次 run 會寫入：

```text
reports/<run_id>/
```

常見輸出：

```text
events.jsonl
recon_report.json
final_report.json
final_report.md
agent_workers/
agent_reports/
success_skill/SKILL.md
```

若成功取得 shell，terminal 會列出：

```text
Shell access: available
Shell attach (...): <attach command>
```

## 安全聲明

本專案只應用於你擁有授權的實驗室、CTF、HTB、內部測試或研究環境。請勿對未授權目標執行掃描、利用或 credential testing。

---

# English

## Overview

**Your Machine is My Machine** is a coordinator-specialist pentest agent for authorized lab targets. It performs recon, creates scoped exploit solver tasks, fans them out through Codex SDK workers, and writes observable reports, shell handoff details, and reusable success skills.

Core workflow:

```text
Recon Agent -> Decision Coordinator -> Solver Fan-Out -> Agent Monitor -> Shell Handoff -> Report
```

LLM / Codex agents produce structured tasks and evidence. Commands are still executed locally, and observable artifacts are saved under the run directory.

## Features

- Recon and service fingerprinting.
- Decision coordinator for next-step exploit planning.
- Codex SDK exploit fan-out with multiple solver agents.
- Web dashboard:
  - Execution Tree
  - Agent Workspaces monitor wall
  - token usage charts
  - final report
  - shell access / attach command
- Final report generation after success or exhaustion.
- Successful chains generate `success_skill/SKILL.md` for future reuse.
- Anthropic and OpenAI-compatible providers.
- Kali / HTB VPN workflow.

## Demo

Demo video will be added here later.

```text
TODO: Add demo video / GIF / asciinema link.
```

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
