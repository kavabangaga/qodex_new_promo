#!/usr/bin/env bash
# Команда приёмнику выкладки на сервере (deploy/server/qodex-release):
#   deploy/ci/remote.sh deploy <id> < site.tar.gz
#   deploy/ci/remote.sh rollback [<id>] < /dev/null
#   deploy/ci/remote.sh status < /dev/null
# Ключ и known_hosts готовит deploy/ci/ssh-setup.sh. Сервер проверяется строго по отпечатку
# из секрета DEPLOY_KNOWN_HOSTS: незнакомый ключ сервера — отказ, без вопросов и без записи в known_hosts.
set -euo pipefail

dir="${RUNNER_TEMP:?нет RUNNER_TEMP}"
: "${DEPLOY_HOST:?нет DEPLOY_HOST}" "${DEPLOY_USER:?нет DEPLOY_USER}"

exec ssh -T \
  -i "$dir/deploy_key" \
  -o IdentitiesOnly=yes \
  -o IdentityAgent=none \
  -o BatchMode=yes \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$dir/known_hosts" \
  -o GlobalKnownHostsFile=/dev/null \
  -o UpdateHostKeys=no \
  -o ConnectTimeout=20 \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=4 \
  -o LogLevel=ERROR \
  "$DEPLOY_USER@$DEPLOY_HOST" "$@"
