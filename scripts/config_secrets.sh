#!/usr/bin/env sh
#
# Prompt for local API secrets and export them into the current shell.
#
# Usage:
#   source scripts/config_secrets.sh
#   ENV=kali source scripts/config_secrets.sh
#
# This script must be sourced. Executing it as ./scripts/config_secrets.sh
# cannot export variables back into the parent shell.

is_sourced=0
(return 0 2>/dev/null) && is_sourced=1

if [ "$is_sourced" -ne 1 ]; then
  printf '[fail] This script must be sourced so exports affect your current shell.\n' >&2
  printf 'Run:\n' >&2
  printf '  source scripts/config_secrets.sh\n' >&2
  printf 'or:\n' >&2
  printf '  ENV=kali source scripts/config_secrets.sh\n' >&2
  exit 2
fi

say_ok() { printf '[ ok ] %s\n' "$1"; }
say_warn() { printf '[warn] %s\n' "$1"; }

_config_secrets_restore_tty() {
  if [ -n "${CONFIG_SECRETS_OLD_STTY:-}" ]; then
    stty "$CONFIG_SECRETS_OLD_STTY" 2>/dev/null
    CONFIG_SECRETS_OLD_STTY=''
  fi
}

_config_secrets_interrupted() {
  _config_secrets_restore_tty
  printf '\n[warn] interrupted; terminal restored\n' >&2
  trap - INT TERM HUP
  return 130 2>/dev/null || exit 130
}

_config_secrets_cleanup() {
  unset is_sourced env_name default_project langsmith_project langsmith_endpoint llm_provider openai_base_url openai_model anthropic_model
  unset CONFIG_SECRETS_READ_VALUE CONFIG_SECRETS_OLD_STTY
  unset -f say_ok say_warn _config_secrets_restore_tty _config_secrets_interrupted _config_secrets_cleanup ask_yes_no read_hidden read_visible_default set_secret_value prompt_secret 2>/dev/null
}

ask_yes_no() {
  local prompt default suffix answer

  prompt="$1"
  default="${2:-n}"
  if [ "$default" = "y" ]; then
    suffix='[Y/n]'
  else
    suffix='[y/N]'
  fi

  printf '%s %s ' "$prompt" "$suffix" >&2
  IFS= read -r answer
  answer="$(printf '%s' "$answer" | tr '[:upper:]' '[:lower:]')"

  if [ -z "$answer" ]; then
    answer="$default"
  fi

  case "$answer" in
    y|yes) return 0 ;;
    *) return 1 ;;
  esac
}

read_hidden() {
  local prompt read_status

  prompt="$1"
  CONFIG_SECRETS_READ_VALUE=''
  printf '%s' "$prompt" >&2

  if [ -n "${BASH_VERSION:-}" ] || [ -n "${ZSH_VERSION:-}" ]; then
    IFS= read -r -s CONFIG_SECRETS_READ_VALUE
    read_status=$?
    printf '\n' >&2
    return "$read_status"
  fi

  CONFIG_SECRETS_OLD_STTY=''
  if [ -t 0 ]; then
    CONFIG_SECRETS_OLD_STTY="$(stty -g 2>/dev/null)"
    stty -echo 2>/dev/null
    trap _config_secrets_interrupted INT TERM HUP
  fi

  IFS= read -r CONFIG_SECRETS_READ_VALUE
  read_status=$?

  if [ -n "$CONFIG_SECRETS_OLD_STTY" ]; then
    _config_secrets_restore_tty
    trap - INT TERM HUP
  fi
  printf '\n' >&2

  return "$read_status"
}

read_visible_default() {
  local prompt default value

  prompt="$1"
  default="$2"
  value=''
  printf '%s [%s]: ' "$prompt" "$default" >&2
  IFS= read -r value
  if [ -z "$value" ]; then
    value="$default"
  fi
  printf '%s' "$value"
}

set_secret_value() {
  local var_name secret_value

  var_name="$1"
  secret_value="$2"

  case "$var_name" in
    ANTHROPIC_API_KEY)
      ANTHROPIC_API_KEY="$secret_value"
      export ANTHROPIC_API_KEY
      ;;
    OPENAI_API_KEY)
      OPENAI_API_KEY="$secret_value"
      export OPENAI_API_KEY
      ;;
    LANGSMITH_API_KEY)
      LANGSMITH_API_KEY="$secret_value"
      export LANGSMITH_API_KEY
      ;;
    *)
      say_warn "unsupported secret variable: $var_name"
      return 1
      ;;
  esac
}

prompt_secret() {
  local var_name label current_value secret_value

  var_name="$1"
  label="$2"
  current_value="$(eval "printf '%s' \"\${$var_name:-}\"")"

  if [ -n "$current_value" ]; then
    if ! ask_yes_no "$label is already set. Replace it?" n; then
      say_ok "$var_name unchanged"
      return 0
    fi
  fi

  if ! read_hidden "Paste $label: "; then
    say_warn "$var_name skipped"
    return 130
  fi

  secret_value="$CONFIG_SECRETS_READ_VALUE"
  if [ -z "$secret_value" ]; then
    say_warn "$var_name skipped"
    return 0
  fi

  set_secret_value "$var_name" "$secret_value" || return 1
  say_ok "$var_name exported"
}

env_name="${ENV:-${PENTEST_ENV:-dev}}"
default_project="pentestagent-$env_name"

llm_provider="${PENTEST_MODEL_PROVIDER:-anthropic}"
if ask_yes_no "Use OpenAI-compatible provider for this shell?" n; then
  llm_provider="openai"
fi

case "$llm_provider" in
  openai|openai-compatible|openai_compatible)
    export PENTEST_MODEL_PROVIDER=openai
    openai_base_url="$(read_visible_default "OpenAI-compatible base URL" "${OPENAI_BASE_URL:-https://api.yunshiuan.com/}")"
    export OPENAI_BASE_URL="$openai_base_url"
    say_ok "OPENAI_BASE_URL=$OPENAI_BASE_URL"

    openai_model="$(read_visible_default "OpenAI-compatible model name" "${PENTEST_MODEL_NAME:-gpt-4.1-mini}")"
    export PENTEST_MODEL_NAME="$openai_model"
    say_ok "PENTEST_MODEL_NAME=$PENTEST_MODEL_NAME"

    if ! prompt_secret OPENAI_API_KEY "OpenAI-compatible API key"; then
      _config_secrets_cleanup
      return 130
    fi
    ;;
  *)
    export PENTEST_MODEL_PROVIDER=anthropic
    anthropic_model="$(read_visible_default "Claude model name" "${PENTEST_MODEL_NAME:-claude-sonnet-4-6}")"
    export PENTEST_MODEL_NAME="$anthropic_model"
    say_ok "PENTEST_MODEL_NAME=$PENTEST_MODEL_NAME"

    if ! prompt_secret ANTHROPIC_API_KEY "Anthropic API key"; then
      _config_secrets_cleanup
      return 130
    fi
    ;;
esac

if [ -n "$PENTEST_MODEL_PROVIDER" ]; then
  say_ok "PENTEST_MODEL_PROVIDER=$PENTEST_MODEL_PROVIDER"
fi

if ask_yes_no "Enable LangSmith Cloud tracing for this shell?" n; then
  export LANGSMITH_TRACING=true
  say_ok "LANGSMITH_TRACING=true"

  if ! prompt_secret LANGSMITH_API_KEY "LangSmith API key"; then
    _config_secrets_cleanup
    return 130
  fi

  if [ -n "${LANGSMITH_PROJECT:-}" ]; then
    default_project="$LANGSMITH_PROJECT"
  fi
  langsmith_project="$(read_visible_default "LangSmith project" "$default_project")"
  export LANGSMITH_PROJECT="$langsmith_project"
  say_ok "LANGSMITH_PROJECT=$LANGSMITH_PROJECT"

  if ask_yes_no "Set a non-default LangSmith endpoint/region?" n; then
    langsmith_endpoint="$(read_visible_default "LangSmith endpoint" "${LANGSMITH_ENDPOINT:-https://api.smith.langchain.com}")"
    export LANGSMITH_ENDPOINT="$langsmith_endpoint"
    say_ok "LANGSMITH_ENDPOINT=$LANGSMITH_ENDPOINT"
  fi
else
  export LANGSMITH_TRACING=false
  say_ok "LANGSMITH_TRACING=false"
fi

printf '\nReady for this shell. Next:\n'
case "$env_name" in
  kali)
    printf '  ./scripts/config_vpn.sh vpn/<profile>.ovpn tun0\n'
    printf '  source .pentestagent-vpn.env\n'
    printf '  ./scripts/preflight.sh\n'
    ;;
  *)
    printf '  ./scripts/preflight.sh\n'
    ;;
esac

_config_secrets_cleanup
