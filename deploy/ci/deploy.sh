#!/usr/bin/env bash
# Выкладка архива на сервер и разбор ответа приёмника (deploy/server/qodex-release).
#   deploy/ci/deploy.sh <номер версии> <архив.tar.gz>
# Код выхода 0 — сайт на сервере переключён на эту версию; 1 — нет, на сайте прежняя версия.
#
# Сверх простого «deploy <id>»:
#   - версия уже есть на сервере (повторный запуск того же коммита — «Re-run» после автоматического отката
#     или Run workflow → deploy): номер версии — время коммита, поэтому повторная сборка даёт тот же номер.
#     В releases/ приёмник кладёт только проверенную целиком сборку — сайт переключается на неё
#     командой rollback <id>;
#   - ответ сервера не дошёл или он ответил «внутренняя ошибка»: спрашиваем status (он ждёт, пока
#     закончится чужое переключение) — несколько раз, если связь не восстановилась сразу.
#
# REMOTE — скрипт связи с сервером (по умолчанию deploy/ci/remote.sh; test-qodex-release.sh подставляет
# вместо него приёмник на своём компьютере). STATUS_TRIES, STATUS_PAUSE — сколько раз и через сколько
# секунд спрашивать status.
set -euo pipefail
export LC_ALL=C

id="${1:?нужен номер версии}"
archive="${2:?нужен архив}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE="${REMOTE:-$here/remote.sh}"
STATUS_TRIES="${STATUS_TRIES:-3}"
STATUS_PAUSE="${STATUS_PAUSE:-15}"

gh() { [[ "${GITHUB_ACTIONS:-}" == true ]]; }
notice() { if gh; then echo "::notice::$*"; else echo "ВНИМАНИЕ: $*"; fi; }
warning() { if gh; then echo "::warning::$*"; else echo "ВНИМАНИЕ: $*"; fi; }
error() { if gh; then echo "::error::$*"; else echo "ОШИБКА: $*"; fi; }

# remote <команда…> — ответ в $out, код в $rc
remote() {
  set +e
  out="$(bash "$REMOTE" "$@" 2>&1)"
  rc=$?
  set -e
  printf '%s\n' "$out"
}

[[ -s "$archive" ]] || { error "нет архива $archive"; exit 1; }
remote deploy "$id" <"$archive"
deploy_rc=$rc
if [[ $rc -eq 0 ]] && grep -qx "OK deploy $id" <<<"$out"; then exit 0; fi

if grep -qF "ERR deploy: версия $id уже есть на сервере" <<<"$out"; then
  notice "Версия $id уже лежит на сервере (повторный запуск) — переключаю сайт на неё: rollback $id"
  remote rollback "$id" </dev/null
  if [[ $rc -eq 0 ]] && grep -qx "OK rollback $id" <<<"$out"; then exit 0; fi
  error "Не удалось переключить сайт на версию $id (код $rc) — на сайте прежняя версия"
  exit 1
fi

# ответ приёмника: отказ по существу (кроме «внутренней ошибки» — она могла случиться и после переключения)
reason="$(grep '^ERR deploy: ' <<<"$out" | tail -n 1 | sed 's/^ERR deploy: //' || true)"
definite=0
if [[ -n "$reason" && "$reason" != внутренняя* ]]; then definite=1; fi

# Какая версия на сервере текущая? status ждёт замок, так что показывает итог уже законченного переключения.
# Связь могла оборваться после того, как архив дошёл целиком, — тогда сервер переключает сайт чуть позже:
# если ответа приёмника нет, спрашиваем несколько раз.
for (( i = 1; i <= STATUS_TRIES; i++ )); do
  remote status </dev/null
  if [[ $rc -eq 0 ]] && grep -qx 'OK status' <<<"$out"; then
    if grep -qx "current $id" <<<"$out"; then
      warning "Ответ сервера на выкладку не дошёл или с ошибкой (код $deploy_rc), но версия $id на сервере текущая"
      exit 0
    fi
    (( definite == 0 )) || break
  fi
  if (( i < STATUS_TRIES )); then sleep "$STATUS_PAUSE"; fi
done

error "Сервер не принял версию $id: ${reason:-нет ответа, код $deploy_rc} — сайт не переключён, на нём прежняя версия"
exit 1
