#!/usr/bin/env bash
#
# Preflight check for running pentestagent on a Kali VM.
# Verifies dependencies, external tools, config, knowledge base, and secrets
# BEFORE you point the agent at a target. Exits non-zero if anything is missing.
#
# Usage:
#   ./scripts/preflight.sh            # check the default 'kali' env
#   ENV=cloud ./scripts/preflight.sh  # check a different config env
#
set -uo pipefail

# Resolve project root (parent of this script's directory).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

ENV_NAME="${ENV:-kali}"

PASS=0
WARN=0
FAIL=0

ok()   { printf '  \033[32m[ ok ]\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
warn() { printf '  \033[33m[warn]\033[0m %s\n' "$1"; WARN=$((WARN+1)); }
bad()  { printf '  \033[31m[fail]\033[0m %s\n' "$1"; FAIL=$((FAIL+1)); }
hdr()  { printf '\n\033[1m%s\033[0m\n' "$1"; }

# --- 1. Python toolchain ---------------------------------------------------
hdr "1. Python toolchain"
if command -v uv >/dev/null 2>&1; then
  ok "uv found ($(uv --version 2>/dev/null))"
else
  bad "uv not found on PATH. Install: https://docs.astral.sh/uv/"
fi

# Runtime + dev deps must import inside the uv env.
if uv run python -c "import chromadb, langgraph, langsmith, pydantic, yaml" 2>/dev/null; then
  ok "runtime deps importable (chromadb, langgraph, langsmith, pydantic, pyyaml)"
else
  bad "runtime deps missing. Run: uv sync"
fi

if uv run python -c "import pytest" 2>/dev/null; then
  ok "dev deps importable (pytest)"
else
  bad "dev deps missing. Run: uv sync --group dev"
fi

# --- 2. External pentest tools on PATH ------------------------------------
hdr "2. External tools on PATH"
# Tools the scan pipeline shells out to directly:
for t in rustscan nmap dirsearch whatweb; do
  if command -v "$t" >/dev/null 2>&1; then ok "$t"; else bad "$t not found (scan pipeline needs it)"; fi
done
# Tools the LLM may propose as commands (allowlisted) but not strictly required:
if command -v searchsploit >/dev/null 2>&1; then
  ok "searchsploit"
else
  warn "searchsploit not found (optional; Kali package: apt-get install -y exploitdb)"
fi

if command -v msfconsole >/dev/null 2>&1; then
  ok "msfconsole"
else
  warn "msfconsole not found (optional; Kali package: apt-get install -y metasploit-framework)"
fi

if command -v curl >/dev/null 2>&1; then
  ok "curl"
else
  warn "curl not found (optional proposal tool; Kali package: apt-get install -y curl)"
fi

# --- 3. Config -------------------------------------------------------------
hdr "3. Config (env: $ENV_NAME)"
if [ -f "config.yaml" ]; then ok "config.yaml present"; else bad "config.yaml missing"; fi
if [ -f "config-${ENV_NAME}.yaml" ]; then
  ok "config-${ENV_NAME}.yaml present"
else
  warn "config-${ENV_NAME}.yaml missing (will fall back to config.yaml defaults)"
fi

# --- 4. Wordlist -----------------------------------------------------------
hdr "4. Wordlist"
WL="$(uv run python -c "from pentestagent.config import Settings; s=Settings.load(env='${ENV_NAME}'); print(s.web_wordlist)" 2>/dev/null)"
if [ -n "$WL" ]; then
  case "$WL" in
    /*) WL_PATH="$WL" ;;
    *)  WL_PATH="$ROOT/$WL" ;;
  esac
  if [ -f "$WL_PATH" ]; then
    ok "wordlist exists: $WL_PATH"
  else
    warn "wordlist missing: $WL_PATH (dirsearch will fail only if web scans need it)"
  fi
else
  warn "could not resolve wordlist path from Settings"
fi

# --- 5. VPN shell context --------------------------------------------------
hdr "5. VPN shell context"
VPN_IFACE="${PENTEST_VPN_INTERFACE:-}"
LHOST="${PENTEST_LHOST:-}"

if [ -z "$VPN_IFACE" ] && [ "$ENV_NAME" = "kali" ]; then
  VPN_IFACE="tun0"
  warn "PENTEST_VPN_INTERFACE not set; checking Kali default: $VPN_IFACE"
fi

if [ -n "$VPN_IFACE" ]; then
  if command -v ip >/dev/null 2>&1; then
    if ip link show "$VPN_IFACE" >/dev/null 2>&1; then
      ok "VPN interface exists: $VPN_IFACE"
    elif [ "$ENV_NAME" = "kali" ]; then
      bad "VPN interface not found: $VPN_IFACE. Run scripts/config_vpn.sh and source .pentestagent-vpn.env"
    else
      warn "VPN interface not found: $VPN_IFACE"
    fi
  else
    warn "ip command not found; cannot verify VPN interface $VPN_IFACE"
  fi
else
  warn "VPN interface not configured; skipping VPN interface check"
fi

if [ -n "$LHOST" ]; then
  ok "LHOST configured: $LHOST"
else
  warn "PENTEST_LHOST not set; run scripts/config_vpn.sh if callback tooling needs it"
fi

# --- 6. Knowledge base + secret -------------------------------------------
hdr "6. Knowledge base & secrets"
if uv run pytest tests/test_knowledge_base.py -q >/dev/null 2>&1; then
  ok "knowledge base validated (chroma store + collection present)"
else
  bad "knowledge base check failed. Run: uv run pytest tests/test_knowledge_base.py -q"
fi

MODEL_PROVIDER="$(uv run python -c "from pentestagent.config import Settings; s=Settings.load(env='${ENV_NAME}'); print(s.model_provider.lower())" 2>/dev/null)"
case "$MODEL_PROVIDER" in
  openai|openai-compatible|openai_compatible)
    ok "model provider: $MODEL_PROVIDER"
    if [ -n "${OPENAI_API_KEY:-}" ]; then
      ok "OPENAI_API_KEY is set"
    else
      warn "OPENAI_API_KEY not set (required for OpenAI-compatible LLM runs unless you run with --no-llm)"
    fi
    ;;
  anthropic|"")
    ok "model provider: ${MODEL_PROVIDER:-anthropic}"
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
      ok "ANTHROPIC_API_KEY is set"
    else
      warn "ANTHROPIC_API_KEY not set (required for Anthropic LLM runs unless you run with --no-llm)"
    fi
    ;;
  *)
    warn "unknown model provider: $MODEL_PROVIDER (ensure the matching API key is exported unless you run with --no-llm)"
    ;;
esac

case "${LANGSMITH_TRACING:-}" in
  1|true|TRUE|yes|YES|on|ON)
    if [ -n "${LANGSMITH_API_KEY:-}" ]; then
      ok "LANGSMITH_API_KEY is set"
    else
      bad "LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is missing"
    fi
    LS_PROJECT="$(uv run python -c "from pentestagent.config import Settings; s=Settings.load(env='${ENV_NAME}'); print(s.langsmith_project or 'default')" 2>/dev/null)"
    if [ -n "$LS_PROJECT" ]; then ok "LangSmith project: $LS_PROJECT"; else warn "could not resolve LangSmith project"; fi
    ;;
  *)
    ok "LangSmith tracing disabled (local reports still written)"
    ;;
esac

# --- 7. Test suite ---------------------------------------------------------
hdr "7. Test suite"
if uv run pytest -q >/dev/null 2>&1; then
  ok "pytest suite passes"
else
  bad "pytest suite failing. Run: uv run pytest -q"
fi

# --- Summary ---------------------------------------------------------------
hdr "Summary"
printf '  pass=%d  warn=%d  fail=%d\n' "$PASS" "$WARN" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf '\n\033[31mNot ready.\033[0m Fix the [fail] items above, then re-run.\n'
  exit 1
fi
printf '\n\033[32mReady.\033[0m First run WITHOUT --auto-approve so you eyeball each proposal:\n'
printf '  uv run python -m pentestagent.main -t <TARGET> --env %s\n' "$ENV_NAME"
[ "$WARN" -gt 0 ] && printf '(Review the [warn] items — they may matter for your run.)\n'
exit 0
