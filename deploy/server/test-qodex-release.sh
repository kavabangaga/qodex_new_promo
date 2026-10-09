#!/usr/bin/env bash
# Проверка приёмника выкладки deploy/server/qodex-release без сервера: вместо /opt/qodex-site —
# временная папка (QODEX_SITE_DIR). Запуск: bash deploy/server/test-qodex-release.sh
#
# Работает в Linux (так её запускает GitHub Actions, .github/workflows/deploy-prod.yml) и в Git Bash
# на Windows. В Git Bash нет flock и настоящих символьных ссылок: ссылки заменяют «системные»
# ссылки Cygwin (MSYS=winsymlinks:sys — их понимают ln, readlink, mv и [[ -L ]]), а flock —
# пустышка, поэтому проверки замка идут только в Linux. Для архивов со ссылками, устройствами,
# путями «..» и особыми правами нужен Python (модуль tarfile); без него эти проверки пропускаются.
# В конце — deploy/ci/deploy.sh (как его запускает GitHub Actions) с приёмником вместо ssh.
set -uo pipefail
export LC_ALL=C

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RECEIVER="$HERE/qodex-release"
PACK="$HERE/../ci/pack.sh"
CI_DEPLOY="$HERE/../ci/deploy.sh"

WORK="$(mktemp -d)"
trap '[[ -n "${KEEP_WORK:-}" ]] || rm -rf "$WORK"' EXIT
export QODEX_SITE_DIR="$WORK/site"
mkdir -p "$QODEX_SITE_DIR"
unset SSH_ORIGINAL_COMMAND SSH_CONNECTION QODEX_MAX_ARCHIVE QODEX_MAX_UNPACKED QODEX_MAX_FILES QODEX_LOCK_WAIT \
  QODEX_RECV_TIMEOUT QODEX_STEP_TIMEOUT GITHUB_ACTIONS

LINUX=1
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    LINUX=0
    export MSYS=winsymlinks:sys CYGWIN=winsymlinks:sys
    ;;
esac
REAL_FLOCK=1
if ! command -v flock >/dev/null 2>&1; then
  REAL_FLOCK=0
  mkdir -p "$WORK/bin"
  printf '#!/bin/sh\nexit 0\n' >"$WORK/bin/flock"
  chmod +x "$WORK/bin/flock"
  export PATH="$WORK/bin:$PATH"
fi
PY=''
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import tarfile' >/dev/null 2>&1; then PY="$c"; break; fi
done

PASS=0
FAILS=0
SKIPS=0
good() { PASS=$((PASS + 1)); echo "  ok    $*"; }
bad() { FAILS=$((FAILS + 1)); echo "  FAIL  $*"; }
skip() { SKIPS=$((SKIPS + 1)); echo "  skip  $*"; }
section() { echo; echo "== $*"; }

# run <файл для stdin | -> <аргументы> — запуск с аргументами, как администратор на сервере
run() {
  local in="$1"
  shift
  [[ "$in" != - ]] || in=/dev/null
  OUT="$(bash "$RECEIVER" "$@" <"$in" 2>"$WORK/stderr")"
  RC=$?
  ERR="$(cat "$WORK/stderr")"
}
# run_ssh <файл для stdin | -> <строка команды> — как запускает sshd по ключу выкладки
run_ssh() {
  local in="$1"
  [[ "$in" != - ]] || in=/dev/null
  OUT="$(SSH_ORIGINAL_COMMAND="$2" SSH_CONNECTION='203.0.113.5 50000 192.0.2.1 22' \
    bash "$RECEIVER" <"$in" 2>"$WORK/stderr")"
  RC=$?
  ERR="$(cat "$WORK/stderr")"
}
# run_quiet <секунд> <аргументы> — стандартный вход открыт, но данные не идут (оборвалась связь)
run_quiet() {
  local quiet="$1"
  shift
  OUT="$({ sleep "$quiet"; } | bash "$RECEIVER" "$@" 2>"$WORK/stderr")"
  RC=$?
  ERR="$(cat "$WORK/stderr")"
}
expect_ok() {
  local name="$1" want="$2"
  if [[ $RC -eq 0 && "$(tail -n 1 <<<"$OUT")" == "$want" ]]; then good "$name"
  else bad "$name — код $RC, вывод «$OUT», ошибки «$ERR»"; fi
}
expect_err() {
  local name="$1" code="$2" text="$3"
  if [[ $RC -eq $code && "$ERR" == ERR* && "$ERR" == *"$text"* ]]; then good "$name"
  else bad "$name — ждали код $code и «$text»; код $RC, вывод «$OUT», ошибки «$ERR»"; fi
}
check() {
  local name="$1"
  shift
  if "$@"; then good "$name"; else bad "$name"; fi
}

id() { printf '20261009-1200%02d-%07x' "$1" "$1"; }
current() { readlink "$QODEX_SITE_DIR/current" 2>/dev/null || echo none; }
releases() { (cd "$QODEX_SITE_DIR/releases" && ls -1) | tr '\n' ' ' | sed 's/ $//'; }
no_incoming() { [[ -z "$(find "$QODEX_SITE_DIR/releases" -maxdepth 1 -name '.incoming-*' -print -quit)" ]]; }
no_uploads() { [[ -z "$(find "$QODEX_SITE_DIR/upload" -mindepth 1 -print -quit 2>/dev/null)" ]]; }

# сайт-заготовка: <папка> <метка>
make_site() {
  rm -rf "$1"
  mkdir -p "$1/_astro" "$1/files" "$1/ro-bot"
  echo "<html>index $2</html>" >"$1/index.html"
  echo "<html>404 $2</html>" >"$1/404.html"
  echo "css $2" >"$1/_astro/app.css"
  echo "pdf $2" >"$1/files/doc.pdf"
  echo "<html>robot $2</html>" >"$1/ro-bot/index.html"
}
# архив как в CI: <метка> → путь к архиву
good_archive() {
  make_site "$WORK/src-$1" "$1"
  bash "$PACK" "$WORK/src-$1" "$WORK/$1.tar.gz" >/dev/null
  echo "$WORK/$1.tar.gz"
}
# MANIFEST.sha256 по текущему содержимому папки, без проверок pack.sh
manifest_of() {
  (cd "$1" && find . -type f ! -path ./MANIFEST.sha256 -print0 | sort -z | xargs -0 -r sha256sum) |
    sed -E 's/^([0-9a-f]{64}) [ *]/\1  /' >"$WORK/manifest.tmp"
  mv "$WORK/manifest.tmp" "$1/MANIFEST.sha256"
}
tar_of() { tar --force-local -C "$1" -czf "$2" .; }

# архив с особой записью (Python tarfile): <вид> <архив>
evil_archive() {
  "$PY" - "$1" "$2" <<'PY'
import hashlib, io, sys, tarfile
kind, out = sys.argv[1], sys.argv[2]
files = {'./index.html': b'<html>evil</html>\n', './404.html': b'<html>404</html>\n'}
extra = {
    'dotdot': ('./../evil.txt', tarfile.REGTYPE),
    'dotdot2': ('./files/../../evil.txt', tarfile.REGTYPE),
    'absolute': ('/tmp/qodex-release-test-evil.txt', tarfile.REGTYPE),
    'symlink': ('./files/link.pdf', tarfile.SYMTYPE),
    'hardlink': ('./files/hard.pdf', tarfile.LNKTYPE),
    'device': ('./files/dev', tarfile.CHRTYPE),
    'fifo': ('./files/fifo', tarfile.FIFOTYPE),
    'space': ('./files/a b.pdf', tarfile.REGTYPE),
    'cyrillic': ('./files/документ.pdf', tarfile.REGTYPE),
    # права: папка без записи или без входа у владельца, файл без записи, setuid
    'rodir': ('./files/', tarfile.DIRTYPE, 0o555),
    'nodir': ('./files/', tarfile.DIRTYPE, 0o000),
    'rofile': ('./files/ro.pdf', tarfile.REGTYPE, 0o444),
    'setuid': ('./files/run.pdf', tarfile.REGTYPE, 0o4755),
}[kind]
manifest = ''.join('%s  %s\n' % (hashlib.sha256(d).hexdigest(), n) for n, d in sorted(files.items()))
with tarfile.open(out, 'w:gz', format=tarfile.GNU_FORMAT) as t:
    def add(name, typ, data=b'', link='', mode=0o644):
        i = tarfile.TarInfo(name)
        i.type = typ
        i.mode = mode
        i.linkname = link
        if typ == tarfile.REGTYPE:
            i.size = len(data)
            t.addfile(i, io.BytesIO(data))
        else:
            t.addfile(i)
    d = tarfile.TarInfo('./'); d.type = tarfile.DIRTYPE; d.mode = 0o755; t.addfile(d)
    for n, data in sorted(files.items()):
        add(n, tarfile.REGTYPE, data)
    add('./MANIFEST.sha256', tarfile.REGTYPE, manifest.encode())
    name, typ, mode = (extra + (None,))[:3]
    if mode is None:
        mode = 0o755 if typ == tarfile.DIRTYPE else 0o644
    add(name, typ, b'evil\n', '/etc/passwd' if typ == tarfile.SYMTYPE else ('./index.html' if typ == tarfile.LNKTYPE else ''), mode)
PY
}

echo "Приёмник: $RECEIVER"
echo "Каталог:  $QODEX_SITE_DIR (Linux: $LINUX, настоящий flock: $REAL_FLOCK, Python: ${PY:-нет})"

# ---------------------------------------------------------------------------------------------------
section "пустой сервер"
run - status
expect_ok "status без версий" "OK status"
check "status: current -" grep -qx 'current -' <<<"$OUT"
run - rollback
expect_err "rollback без версий" 1 "нет предыдущей версии"

# ---------------------------------------------------------------------------------------------------
section "отказ на неверные команды"
run_ssh - ''
expect_err "пустая команда (вход без команды)" 2 "пустая команда"
run_ssh - 'bash'
expect_err "чужая команда" 2 "неизвестная команда"
run_ssh - 'status; rm -rf /'
expect_err "попытка дописать команду через ;" 2 "недопустимая команда"
# shellcheck disable=SC2016 # подстановка нарочно не раскрывается: так строку прислал бы злоумышленник
run_ssh - 'deploy $(id)'
expect_err "подстановка команды" 2 "недопустимая команда"
run_ssh - 'deploy ../../etc'
expect_err "путь вместо номера" 2 "недопустимая команда"
run_ssh - 'deploy 2026-bad'
expect_err "неверный номер версии" 2 "неверный номер версии"
run_ssh - "deploy $(id 1) extra"
expect_err "лишний аргумент deploy" 2 "нужно: deploy <id>"
run_ssh - 'status now'
expect_err "лишний аргумент status" 2 "нужно: status"
run_ssh - "rollback $(id 1) $(id 2)"
expect_err "лишний аргумент rollback" 2 "нужно: rollback"
run_ssh - "rollback 20261009"
expect_err "неверный номер в rollback" 2 "неверный номер версии"
run_ssh - "$(printf 'x%.0s' {1..250})"
expect_err "слишком длинная команда" 2 "недопустимая команда"

# ---------------------------------------------------------------------------------------------------
section "хорошая выкладка"
A1="$(good_archive one)"
run_ssh "$A1" "deploy $(id 1)"
expect_ok "deploy $(id 1)" "OK deploy $(id 1)"
check "current → releases/$(id 1)" test "$(current)" == "releases/$(id 1)"
check "через current виден index.html" grep -q 'index one' "$QODEX_SITE_DIR/current/index.html"
check "MANIFEST.sha256 лежит в версии" test -f "$QODEX_SITE_DIR/releases/$(id 1)/MANIFEST.sha256"
check "временных .incoming-* нет" no_incoming
if (( LINUX )); then
  check "файлы 644" test "$(stat -c %a "$QODEX_SITE_DIR/current/_astro/app.css")" == 644
  check "папки 755" test "$(stat -c %a "$QODEX_SITE_DIR/releases/$(id 1)/_astro")" == 755
else
  skip "права 644/755 (только в Linux)"
fi
run_ssh "$A1" "deploy $(id 1)"
expect_err "повторная выкладка того же номера" 1 "уже есть"
run - deploy "$(id 9)"
expect_err "deploy без архива" 1 "пустой архив"

# ---------------------------------------------------------------------------------------------------
section "испорченные архивы (сайт не должен переключиться)"
before="$(current)"

make_site "$WORK/bad-sum" badsum
manifest_of "$WORK/bad-sum"
echo "подмена" >>"$WORK/bad-sum/ro-bot/index.html"
tar_of "$WORK/bad-sum" "$WORK/bad-sum.tar.gz"
run "$WORK/bad-sum.tar.gz" deploy "$(id 50)"
expect_err "неверная контрольная сумма" 1 "контрольные суммы не сходятся"

make_site "$WORK/extra" extra
manifest_of "$WORK/extra"
echo "лишний" >"$WORK/extra/files/extra.pdf"
tar_of "$WORK/extra" "$WORK/extra.tar.gz"
run "$WORK/extra.tar.gz" deploy "$(id 51)"
expect_err "файл не из MANIFEST.sha256" 1 "не совпадает со списком"

make_site "$WORK/no-manifest" nomanifest
tar_of "$WORK/no-manifest" "$WORK/no-manifest.tar.gz"
run "$WORK/no-manifest.tar.gz" deploy "$(id 52)"
expect_err "нет MANIFEST.sha256" 1 "нет MANIFEST.sha256"

make_site "$WORK/no-index" noindex
rm "$WORK/no-index/index.html"
manifest_of "$WORK/no-index"
tar_of "$WORK/no-index" "$WORK/no-index.tar.gz"
run "$WORK/no-index.tar.gz" deploy "$(id 53)"
expect_err "нет index.html" 1 "нет index.html"

make_site "$WORK/no-404" no404
rm "$WORK/no-404/404.html"
manifest_of "$WORK/no-404"
tar_of "$WORK/no-404" "$WORK/no-404.tar.gz"
run "$WORK/no-404.tar.gz" deploy "$(id 54)"
expect_err "нет 404.html" 1 "нет 404.html"

echo "это не архив" >"$WORK/text.tar.gz"
run "$WORK/text.tar.gz" deploy "$(id 55)"
expect_err "не gzip" 1 "повреждён"

head -c "$(($(stat -c %s "$A1") / 2))" "$A1" >"$WORK/half.tar.gz"
run "$WORK/half.tar.gz" deploy "$(id 56)"
expect_err "оборванный архив" 1 "повреждён"

QODEX_MAX_ARCHIVE=100 run "$A1" deploy "$(id 57)"
expect_err "архив больше предела" 1 "архив больше"
QODEX_MAX_FILES=3 run "$A1" deploy "$(id 58)"
expect_err "записей больше предела" 1 "записей"
QODEX_MAX_UNPACKED=10 run "$A1" deploy "$(id 59)"
expect_err "после распаковки больше предела" 1 "после распаковки"

# записей много: счёт идёт потоком и обрывается на пределе, весь список в память не читается
mkdir -p "$WORK/many"
(cd "$WORK/many" && seq 1 3000 | sed 's/^/f/' | xargs touch)
tar_of "$WORK/many" "$WORK/many.tar.gz"
QODEX_MAX_FILES=100 run "$WORK/many.tar.gz" deploy "$(id 78)"
expect_err "3000 записей при пределе 100" 1 "больше 100 записей"

# MANIFEST.sha256 со строкой «..»: отказ раньше, чем sha256sum откроет файл по ней (вне версии
# или /dev/zero, на котором проверка повисла бы, держа замок)
fake_sum="$(printf '%064d' 0)"
make_site "$WORK/m-dotdot" mdotdot
manifest_of "$WORK/m-dotdot"
echo "$fake_sum  ./../../log/deploy.log" >>"$WORK/m-dotdot/MANIFEST.sha256"
tar_of "$WORK/m-dotdot" "$WORK/m-dotdot.tar.gz"
run "$WORK/m-dotdot.tar.gz" deploy "$(id 69)"
expect_err "MANIFEST.sha256: файл вне версии (./../)" 1 "MANIFEST.sha256: путь с «..»"

make_site "$WORK/m-zero" mzero
manifest_of "$WORK/m-zero"
echo "$fake_sum  ./../../../../../../../../../../../../dev/zero" >>"$WORK/m-zero/MANIFEST.sha256"
tar_of "$WORK/m-zero" "$WORK/m-zero.tar.gz"
started=$SECONDS
QODEX_STEP_TIMEOUT=60 run "$WORK/m-zero.tar.gz" deploy "$(id 70)"
expect_err "MANIFEST.sha256: /dev/zero через «..»" 1 "MANIFEST.sha256: путь с «..»"
check "отказ сразу, без чтения /dev/zero" test $((SECONDS - started)) -lt 30

# список сверяется раньше сумм: файла нет в списке, а у другого неверная сумма — ответ про список
make_site "$WORK/m-order" morder
manifest_of "$WORK/m-order"
grep -v './files/doc.pdf$' "$WORK/m-order/MANIFEST.sha256" >"$WORK/m-order/m.tmp"
mv "$WORK/m-order/m.tmp" "$WORK/m-order/MANIFEST.sha256"
echo "подмена" >>"$WORK/m-order/index.html"
tar_of "$WORK/m-order" "$WORK/m-order.tar.gz"
run "$WORK/m-order.tar.gz" deploy "$(id 71)"
expect_err "список проверяется раньше контрольных сумм" 1 "не совпадает со списком"

# стандартный вход открыт, а архив не идёт — приём обрывается по времени, замок при этом не взят
QODEX_RECV_TIMEOUT=1 run_quiet 4 deploy "$(id 73)"
expect_err "архив не пришёл за отведённое время" 1 "не пришёл за 1 с"

if [[ -n "$PY" ]]; then
  for kind in dotdot dotdot2 absolute symlink hardlink device fifo space cyrillic rodir nodir rofile setuid; do
    evil_archive "$kind" "$WORK/evil-$kind.tar.gz"
  done
  run "$WORK/evil-dotdot.tar.gz" deploy "$(id 60)"
  expect_err "путь ./../ в архиве" 1 "«..»"
  run "$WORK/evil-dotdot2.tar.gz" deploy "$(id 61)"
  expect_err "путь files/../../ в архиве" 1 "«..»"
  run "$WORK/evil-absolute.tar.gz" deploy "$(id 62)"
  expect_err "абсолютный путь в архиве" 1 "абсолютный путь"
  run "$WORK/evil-symlink.tar.gz" deploy "$(id 63)"
  expect_err "символьная ссылка в архиве" 1 "особые записи"
  run "$WORK/evil-hardlink.tar.gz" deploy "$(id 64)"
  expect_err "жёсткая ссылка в архиве" 1 "особые записи"
  run "$WORK/evil-device.tar.gz" deploy "$(id 65)"
  expect_err "устройство в архиве" 1 "особые записи"
  run "$WORK/evil-fifo.tar.gz" deploy "$(id 66)"
  expect_err "канал (fifo) в архиве" 1 "особые записи"
  run "$WORK/evil-space.tar.gz" deploy "$(id 67)"
  expect_err "пробел в имени файла" 1 "недопустимые символы"
  run "$WORK/evil-cyrillic.tar.gz" deploy "$(id 68)"
  expect_err "кириллица в имени файла" 1 "недопустимые символы"
  run "$WORK/evil-rodir.tar.gz" deploy "$(id 74)"
  expect_err "папка без права записи (555)" 1 "права записей"
  run "$WORK/evil-nodir.tar.gz" deploy "$(id 75)"
  expect_err "папка без прав (000)" 1 "права записей"
  run "$WORK/evil-rofile.tar.gz" deploy "$(id 76)"
  expect_err "файл без права записи (444)" 1 "права записей"
  run "$WORK/evil-setuid.tar.gz" deploy "$(id 77)"
  expect_err "файл с setuid" 1 "права записей"
  check "файл вне папки не создан (..)" test ! -e "$WORK/evil.txt" -a ! -e "$QODEX_SITE_DIR/evil.txt" -a ! -e "$QODEX_SITE_DIR/releases/evil.txt"
  check "файл вне папки не создан (/tmp)" test ! -e /tmp/qodex-release-test-evil.txt
else
  skip "архивы с «..», ссылками и устройствами (нет Python)"
fi

check "сайт не переключился" test "$(current)" == "$before"
check "временных .incoming-* нет" no_incoming
check "принятых архивов в upload/ не осталось" no_uploads
check "в releases только $(id 1)" test "$(releases)" == "$(id 1)"

# ---------------------------------------------------------------------------------------------------
section "откат"
run_ssh "$(good_archive two)" "deploy $(id 2)"
expect_ok "deploy $(id 2)" "OK deploy $(id 2)"
run_ssh - status
expect_ok "status" "OK status"
check "status: current $(id 2)" grep -qx "current $(id 2)" <<<"$OUT"
check "status: previous $(id 1)" grep -qx "previous $(id 1)" <<<"$OUT"
check "status: release $(id 2) current" grep -qx "release $(id 2) current" <<<"$OUT"
check "status: release $(id 1) previous" grep -qx "release $(id 1) previous" <<<"$OUT"

run_ssh - rollback
expect_ok "rollback → предыдущая" "OK rollback $(id 1)"
check "current → $(id 1)" test "$(current)" == "releases/$(id 1)"
check "через current снова старый index.html" grep -q 'index one' "$QODEX_SITE_DIR/current/index.html"
run_ssh - rollback
expect_ok "повторный rollback возвращает обратно" "OK rollback $(id 2)"
run_ssh - "rollback $(id 1)"
expect_ok "rollback на указанную версию" "OK rollback $(id 1)"
run_ssh - "rollback $(id 1)"
expect_ok "rollback на текущую — ничего не меняет" "OK rollback $(id 1)"
check "current → $(id 1)" test "$(current)" == "releases/$(id 1)"
run_ssh - "rollback $(id 40)"
expect_err "rollback на версию, которой нет" 1 "нет на сервере"
run_ssh - "rollback $(id 2)"
expect_ok "rollback на $(id 2)" "OK rollback $(id 2)"

# ---------------------------------------------------------------------------------------------------
section "чистка старых версий"
for n in 3 4 5 6 7 8 9; do
  run_ssh "$(good_archive "r$n")" "deploy $(id "$n")"
  [[ $RC -eq 0 ]] || bad "deploy $(id "$n") — $ERR"
done
check "осталось 5 последних" test "$(releases)" == "$(id 5) $(id 6) $(id 7) $(id 8) $(id 9)"
check "current → $(id 9)" test "$(current)" == "releases/$(id 9)"

run_ssh - "rollback $(id 5)"
expect_ok "rollback на самую старую из оставшихся" "OK rollback $(id 5)"
run_ssh "$(good_archive r10)" "deploy $(id 10)"
expect_ok "deploy $(id 10)" "OK deploy $(id 10)"
check "предыдущая ($(id 5)) не удалена, хоть и шестая" test "$(releases)" == "$(id 5) $(id 6) $(id 7) $(id 8) $(id 9) $(id 10)"
run_ssh - rollback
expect_ok "rollback после чистки" "OK rollback $(id 5)"
run_ssh - rollback
expect_ok "и обратно" "OK rollback $(id 10)"
run_ssh "$(good_archive r11)" "deploy $(id 11)"
expect_ok "deploy $(id 11)" "OK deploy $(id 11)"
check "снова 5 последних" test "$(releases)" == "$(id 7) $(id 8) $(id 9) $(id 10) $(id 11)"

# ---------------------------------------------------------------------------------------------------
section "прерванная выкладка, сломанный current, ссылки в releases, замок"
# след прерванной выкладки с папкой без права записи (chmod 555) — уборка не должна на нём падать
stale="$QODEX_SITE_DIR/releases/.incoming-$(id 70)"
mkdir -p "$stale/sub/deep"
echo x >"$stale/sub/deep/file"
chmod 555 "$stale/sub/deep" "$stale/sub"
echo x >"$QODEX_SITE_DIR/releases/.incoming-$(id 70).tar.gz"
# в upload/: архив, брошенный давно, и свежий — его может прямо сейчас принимать другой deploy
mkdir -p "$QODEX_SITE_DIR/upload"
echo old >"$QODEX_SITE_DIR/upload/$(id 70).OLDOLDOL"
touch -d '-2 hours' "$QODEX_SITE_DIR/upload/$(id 70).OLDOLDOL"
echo fresh >"$QODEX_SITE_DIR/upload/$(id 72).FRESHFRE"
run_ssh "$(good_archive r12)" "deploy $(id 12)"
expect_ok "deploy после прерванной выкладки" "OK deploy $(id 12)"
check "следы прерванной выкладки убраны (и папка без права записи)" no_incoming
check "давний архив в upload/ убран" test ! -e "$QODEX_SITE_DIR/upload/$(id 70).OLDOLDOL"
check "свежий архив в upload/ не тронут" test -e "$QODEX_SITE_DIR/upload/$(id 72).FRESHFRE"
rm -f "$QODEX_SITE_DIR/upload/$(id 72).FRESHFRE"

OTHER="$WORK/other"
mkdir -p "$OTHER/current"
QODEX_SITE_DIR="$OTHER" run "$(good_archive r13)" deploy "$(id 13)"
expect_err "current — папка, а не ссылка" 1 "не символьная ссылка"

# releases/<номер> — символьная ссылка (её мог оставить человек на сервере): сайт на неё не переключается
ln -s "$QODEX_SITE_DIR/releases/$(id 11)" "$QODEX_SITE_DIR/releases/$(id 97)"
mkdir -p "$WORK/outside-site"
echo '<html>outside</html>' >"$WORK/outside-site/index.html"
ln -s "$WORK/outside-site" "$QODEX_SITE_DIR/releases/$(id 98)"
run_ssh - "rollback $(id 97)"
expect_err "rollback на ссылку на другую версию" 1 "символьная ссылка"
run_ssh - "rollback $(id 98)"
expect_err "rollback на ссылку вне releases" 1 "символьная ссылка"
check "сайт не переключился" test "$(current)" == "releases/$(id 12)"
run_ssh - status
check "status не показывает ссылки" test -z "$(grep -e "$(id 97)" -e "$(id 98)" <<<"$OUT")"
run_ssh "$(good_archive r98)" "deploy $(id 98)"
expect_err "deploy с номером ссылки" 1 "уже есть"
rm -f "$QODEX_SITE_DIR/releases/$(id 97)" "$QODEX_SITE_DIR/releases/$(id 98)"
check "версия под ссылкой цела" test -f "$QODEX_SITE_DIR/releases/$(id 11)/index.html"

if (( REAL_FLOCK )); then
  flock "$QODEX_SITE_DIR/.lock" sleep 8 &
  holder=$!
  sleep 1
  QODEX_LOCK_WAIT=1 run_ssh "$(good_archive r14)" "deploy $(id 14)"
  expect_err "вторая выкладка ждёт замок и отказывается" 1 "занято"
  QODEX_LOCK_WAIT=1 run_ssh - status
  expect_err "status не дождался замка — «занято»" 1 "занято"
  started=$SECONDS
  QODEX_LOCK_WAIT=30 run_ssh - status
  expect_ok "status дождался конца чужого переключения" "OK status"
  check "status ждал замок" test $((SECONDS - started)) -ge 2
  wait "$holder"

  # медленная загрузка архива замок не держит: пока архив идёт, status и rollback работают
  slow_archive="$(good_archive r15)"
  { sleep 4; cat "$slow_archive"; } | bash "$RECEIVER" deploy "$(id 15)" >"$WORK/slow.out" 2>&1 &
  slow=$!
  sleep 1
  QODEX_LOCK_WAIT=1 run_ssh - status
  expect_ok "status во время медленной загрузки" "OK status"
  QODEX_LOCK_WAIT=1 run_ssh - "rollback $(id 11)"
  expect_ok "rollback во время медленной загрузки" "OK rollback $(id 11)"
  wait "$slow"
  check "медленная выкладка дошла" grep -qx "OK deploy $(id 15)" "$WORK/slow.out"
else
  skip "замок flock: выкладка, status, медленная загрузка (только в Linux)"
fi

# ---------------------------------------------------------------------------------------------------
section "порядок версий: старше текущей deploy не принимает, rollback — как прежде"
MAIN_DIR="$QODEX_SITE_DIR"
export QODEX_SITE_DIR="$WORK/order"
mkdir -p "$QODEX_SITE_DIR"
run_ssh "$(good_archive o5)" "deploy $(id 5)"
expect_ok "deploy $(id 5)" "OK deploy $(id 5)"
run_ssh "$(good_archive o3)" "deploy $(id 3)"
expect_err "сборка старого коммита после нового — отказ" 1 "старше текущей $(id 5)"
check "сайт остался на $(id 5)" test "$(current)" == "releases/$(id 5)"
check "в releases только $(id 5)" test "$(releases)" == "$(id 5)"
check "принятых архивов в upload/ не осталось" no_uploads
run_ssh "$(good_archive o6)" "deploy $(id 6)"
expect_ok "deploy $(id 6)" "OK deploy $(id 6)"
run_ssh - "rollback $(id 5)"
expect_ok "rollback на более старую версию — можно" "OK rollback $(id 5)"
run_ssh "$(good_archive o4)" "deploy $(id 4)"
expect_err "после отката: версия старше текущей — отказ" 1 "старше текущей $(id 5)"
same="20261009-120005-abcdef1"
run_ssh "$(good_archive o5b)" "deploy $same"
expect_ok "та же секунда коммита, другой коммит — принимается" "OK deploy $same"
run_ssh "$(good_archive o6b)" "deploy $(id 6)"
expect_err "повторная выкладка номера, который уже есть" 1 "уже есть"

# ---------------------------------------------------------------------------------------------------
section "deploy/ci/deploy.sh — выкладка из GitHub Actions (приёмник вместо ssh)"
export QODEX_SITE_DIR="$WORK/ci"
mkdir -p "$QODEX_SITE_DIR"
printf '#!/usr/bin/env bash\nexec bash %q "$@"\n' "$RECEIVER" >"$WORK/remote-local.sh"
# ответ на deploy теряется (связь оборвалась после переключения)
printf '#!/usr/bin/env bash\nif [[ $1 == deploy ]]; then bash %q "$@" >/dev/null 2>&1; exit 255; fi\nexec bash %q "$@"\n' \
  "$RECEIVER" "$RECEIVER" >"$WORK/remote-lost.sh"
# до сервера на deploy не достучаться
printf '#!/usr/bin/env bash\nif [[ $1 == deploy ]]; then echo "ssh: connect to host: Connection timed out" >&2; exit 255; fi\nexec bash %q "$@"\n' \
  "$RECEIVER" >"$WORK/remote-dead.sh"
ci() {
  local remote="$1"
  shift
  CI_OUT="$(REMOTE="$WORK/remote-$remote.sh" STATUS_TRIES=2 STATUS_PAUSE=0 bash "$CI_DEPLOY" "$@" 2>&1)"
  CI_RC=$?
}
ci_expect() {
  local name="$1" code="$2" text="$3"
  if [[ $CI_RC -eq $code && "$CI_OUT" == *"$text"* ]]; then good "$name"
  else bad "$name — ждали код $code и «$text»; код $CI_RC, вывод «$CI_OUT»"; fi
}
ci local "$(id 20)" "$(good_archive c20)"
ci_expect "выкладка" 0 "OK deploy $(id 20)"
ci local "$(id 20)" "$(good_archive c20)"
ci_expect "повторный запуск: версия уже есть — переключение на неё" 0 "OK rollback $(id 20)"
check "  и в выводе понятно, что произошло" grep -q "уже лежит на сервере" <<<"$CI_OUT"
ci local "$(id 21)" "$(good_archive c21)"
ci_expect "выкладка $(id 21)" 0 "OK deploy $(id 21)"
run_ssh - rollback
expect_ok "автоматический откат после неудачной проверки" "OK rollback $(id 20)"
ci local "$(id 21)" "$(good_archive c21)"
ci_expect "Re-run после отката: сайт снова на $(id 21)" 0 "OK rollback $(id 21)"
check "current → $(id 21)" test "$(current)" == "releases/$(id 21)"
echo "это не архив" >"$WORK/c22.tar.gz"
ci local "$(id 22)" "$WORK/c22.tar.gz"
ci_expect "испорченный архив — ошибка" 1 "Сервер не принял версию $(id 22)"
ci local "$(id 19)" "$(good_archive c19)"
ci_expect "версия старше текущей — ошибка" 1 "старше текущей"
ci lost "$(id 23)" "$(good_archive c23)"
ci_expect "ответ не дошёл, но сайт переключён — успех" 0 "версия $(id 23) на сервере текущая"
ci dead "$(id 24)" "$(good_archive c24)"
ci_expect "до сервера не достучаться — ошибка" 1 "нет ответа, код 255"
check "  status спрошен 2 раза (STATUS_TRIES)" test "$(grep -c '^OK status$' <<<"$CI_OUT")" -eq 2
check "сайт остался на $(id 23)" test "$(current)" == "releases/$(id 23)"
export QODEX_SITE_DIR="$MAIN_DIR"

# ---------------------------------------------------------------------------------------------------
section "журнал"
LOG="$QODEX_SITE_DIR/log/deploy.log"
check "журнал есть" test -s "$LOG"
check "в журнале выкладка с адресом" grep -q "\[203.0.113.5\] OK deploy $(id 1)" "$LOG"
check "в журнале отказ" grep -q 'ERR command: недопустимая команда' "$LOG"
check "в журнале переключение" grep -q "switch $(id 1) -> $(id 2)" "$LOG"
check "в журнале чистка" grep -q "prune $(id 1)" "$LOG"
check "присланная строка в журнале обезврежена" grep -qF 'недопустимая команда: status? rm -rf ?' "$LOG"
check "опасные символы в журнал не попали" bash -c "! grep -qF -e 'status; rm' -e '\$(id)' '$LOG'"

echo
echo "Итого: пройдено $PASS, не пройдено $FAILS, пропущено $SKIPS"
(( FAILS == 0 ))
