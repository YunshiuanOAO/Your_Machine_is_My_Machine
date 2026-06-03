# ADR-05: CLI Runbook and Auto-Approve Mode

Date: 2026-06-03

Status: Accepted

## Context

The operator workflow now uses several command-line entry points:

- Docker/Kali setup for local HTB testing;
- shell-owned secret setup;
- shell-owned VPN setup;
- executable preflight;
- the Python agent CLI;
- optional no-LLM, artifact-backed, and auto-approved run modes.

We need one command catalog that explains the expected order and the supported way to run without the interactive human approval prompt.

## Decision

The v1 CLI workflow remains shell-first and explicit:

1. prepare the environment;
2. export secrets into the current shell;
3. establish VPN when needed;
4. run preflight;
5. run the agent.

Human command approval remains the default for live runs. Auto-approve mode is supported for trusted lab automation after the operator has already validated behavior manually.

Auto-approve means the approval prompt is skipped. It does not bypass executor safety checks: allowlisted tools, non-interactive execution, shell-metacharacter blocking, target placeholder substitution, timeouts, and artifact logging still apply.

## Command Catalog

### Local Docker Kali

Build and start the local Kali attack box:

```bash
docker compose up -d --build
docker compose ps
```

SSH into the container:

```bash
ssh -p 2222 root@localhost
# password: kali
cd /app
```

If SSH host keys changed after rebuilding the container:

```bash
ssh-keygen -R '[localhost]:2222'
ssh -p 2222 root@localhost
```

### Dependencies

Runtime only:

```bash
uv sync
```

Runtime plus local tests/preflight:

```bash
uv sync --group dev
```

Optional Kali proposal tools:

```bash
apt-get update
apt-get install -y exploitdb metasploit-framework
```

On a normal non-root Kali VM shell, prefix the apt commands with `sudo`.

### Secrets

Prompt for secrets and export them into the current shell:

```bash
source scripts/config_secrets.sh
```

For Kali/HTB, use:

```bash
ENV=kali source scripts/config_secrets.sh
```

The script must be sourced. Executing it as `./scripts/config_secrets.sh` cannot export variables back into the parent shell.

Equivalent manual exports:

```bash
export ANTHROPIC_API_KEY="..."
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY="..."
export LANGSMITH_PROJECT=pentestagent-kali
```

Leave `LANGSMITH_TRACING` unset or `false` for local-only traces.

### VPN

Start the VPN and write shell exports:

```bash
./scripts/config_vpn.sh vpn/<profile>.ovpn tun0
source .pentestagent-vpn.env
```

The Python agent does not configure VPN, routes, interfaces, or `LHOST`.

### Preflight

Default Kali preflight:

```bash
./scripts/preflight.sh
```

Preflight for another config environment:

```bash
ENV=dev ./scripts/preflight.sh
```

Preflight must pass before a live target run. Warnings for `searchsploit` and `msfconsole` are optional proposal-tool warnings; hard scan tools must be present.

### Agent CLI

Main live Kali run with human approval:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

Run without scanning:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --skip-scan
```

Run with existing scan artifacts:

```bash
uv run python -m pentestagent.main \
  -t <TARGET_IP> \
  --env kali \
  --rustscan-file path/to/rustscan_output.json \
  --dirsearch-file path/to/dirsearch_output.json
```

Run without LLM calls:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --no-llm
```

Override retry budget:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --max-retries 6
```

## No Human Approval Mode

The supported one-off command is:

```bash
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --auto-approve
```

For shell automation, the equivalent environment variable is:

```bash
export PENTEST_AUTO_APPROVE=true
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

`--auto-approve` is preferred for one run because it is visible in shell history and does not silently affect later runs. `PENTEST_AUTO_APPROVE=true` is useful for controlled automation, but the operator must unset it before returning to manual mode:

```bash
unset PENTEST_AUTO_APPROVE
```

Auto-approve only skips `services/approval.py`'s prompt. The executor still blocks:

- tools outside `tools.allowed`;
- proposals with `requires_interactive: true`;
- shell metacharacters in arguments, such as `;`, `&&`, `|`, backticks, `$(`, `>`, or `<`;
- commands that exceed the configured timeout.

All command proposals, executions, blocked commands, stdout/stderr paths, and final reports remain recorded under `reports/<run_id>/`.

## Recommended Kali Order

Manual first run:

```bash
cd /app
uv sync --group dev
ENV=kali source scripts/config_secrets.sh
./scripts/config_vpn.sh vpn/<profile>.ovpn tun0
source .pentestagent-vpn.env
./scripts/preflight.sh
uv run python -m pentestagent.main -t <TARGET_IP> --env kali
```

Trusted lab run without the approval prompt:

```bash
cd /app
ENV=kali source scripts/config_secrets.sh
./scripts/config_vpn.sh vpn/<profile>.ovpn tun0
source .pentestagent-vpn.env
./scripts/preflight.sh
uv run python -m pentestagent.main -t <TARGET_IP> --env kali --auto-approve
```

## CLI Flags

The Python CLI is `uv run python -m pentestagent.main`.

- `-t`, `--target`: required target IP or host.
- `--env`: config environment name, such as `dev` or `kali`.
- `--rustscan-file`: use an existing RustScan/Nmap JSON artifact.
- `--dirsearch-file`: use an existing Dirsearch JSON artifact.
- `--skip-scan`: do not run the scanner when artifacts are missing.
- `--auto-approve`: approve generated command proposals without prompting.
- `--max-retries`: override the configured global retry-cycle budget.
- `--no-llm`: use deterministic fallbacks instead of Claude calls.

## Consequences

Positive:

- Operators have a single command reference for setup, preflight, and agent execution.
- Auto-approve mode is explicit and easy to audit in shell history.
- CI/lab automation can avoid blocking on an interactive prompt.

Negative:

- Auto-approve can execute target-affecting commands proposed by the LLM without per-command review.
- Operators must remember to unset `PENTEST_AUTO_APPROVE` if they used the environment variable form.

## Guardrails

- Keep `execution.auto_approve: false` in checked-in Kali config.
- First live runs should use manual approval.
- Use `--auto-approve` only on authorized lab targets after preflight passes.
- Do not enable interactive commands in v1.
- Do not store `ANTHROPIC_API_KEY` or `LANGSMITH_API_KEY` in YAML.

## Validation

Static checks:

```bash
bash -n scripts/config_secrets.sh
bash -n scripts/config_vpn.sh
bash -n scripts/preflight.sh
bash -n scripts/msfinstall.sh
```

Unit suite:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q
```
