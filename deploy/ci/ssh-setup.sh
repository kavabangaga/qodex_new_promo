#!/usr/bin/env bash
# Ключ выкладки и отпечаток сервера для ssh — во временной папке задания GitHub Actions.
# Берёт секреты DEPLOY_SSH_KEY (закрытый ключ) и DEPLOY_KNOWN_HOSTS (строка known_hosts сервера)
# и переменные DEPLOY_HOST, DEPLOY_USER из окружения шага. Ключ удаляет шаг «Убрать ключ»
# в конце задания (и сам GitHub вместе с временной папкой).
set -euo pipefail

dir="${RUNNER_TEMP:?нет RUNNER_TEMP}"
fail() { echo "::error::$*"; exit 1; }

[[ -n "${DEPLOY_SSH_KEY:-}" ]] || fail "нет секрета DEPLOY_SSH_KEY (Settings → Environments → production → Secrets)"
[[ -n "${DEPLOY_KNOWN_HOSTS:-}" ]] || fail "нет секрета DEPLOY_KNOWN_HOSTS"
[[ "${DEPLOY_HOST:-}" =~ ^[A-Za-z0-9.-]+$ ]] || fail "нет или неверна переменная DEPLOY_HOST"
[[ "${DEPLOY_USER:-}" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "нет или неверна переменная DEPLOY_USER"

umask 077
# \r — если секрет вставили из файла с переводами строк Windows
printf '%s\n' "$DEPLOY_SSH_KEY" | tr -d '\r' >"$dir/deploy_key"
printf '%s\n' "$DEPLOY_KNOWN_HOSTS" | tr -d '\r' >"$dir/known_hosts"
chmod 600 "$dir/deploy_key" "$dir/known_hosts"

grep -q 'PRIVATE KEY-----' "$dir/deploy_key" || fail "DEPLOY_SSH_KEY не похож на закрытый ключ"
ssh-keygen -y -f "$dir/deploy_key" >/dev/null 2>&1 || fail "DEPLOY_SSH_KEY не читается (ключ с паролем или повреждён)"
grep -Eq "^(\[?$DEPLOY_HOST\]?(:[0-9]+)?[ ,]|\|1\|)" "$dir/known_hosts" ||
  fail "в DEPLOY_KNOWN_HOSTS нет строки для $DEPLOY_HOST"

echo "Отпечаток сервера, которому доверяем:"
ssh-keygen -l -f "$dir/known_hosts"
