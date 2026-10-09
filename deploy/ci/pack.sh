#!/usr/bin/env bash
# Упаковка собранного сайта для выкладки на сервер.
#   deploy/ci/pack.sh <папка сборки> <архив.tar.gz>
# Кладёт в папку сборки MANIFEST.sha256 (контрольная сумма каждого файла, строки «<sha256>  ./путь»)
# и собирает архив: внутри только обычные файлы и папки, владелец 0/0. Приёмник на сервере
# (deploy/server/qodex-release) проверяет по MANIFEST.sha256 каждый файл и отказывается от архива,
# где файлов больше или меньше, чем в списке.
set -euo pipefail
export LC_ALL=C

dist="${1:?нужна папка сборки}"
out="${2:?нужен путь к архиву}"

[[ -f "$dist/index.html" ]] || { echo "pack: нет $dist/index.html" >&2; exit 1; }
if [[ -n "$(find "$dist" -mindepth 1 ! -type f ! -type d -print -quit)" ]]; then
  echo "pack: в сборке есть символьные ссылки или особые файлы" >&2
  exit 1
fi

manifest="$(mktemp)"
trap 'rm -f "$manifest"' EXIT
rm -f "$dist/MANIFEST.sha256"
# sha256sum в Git Bash пишет «хеш *имя» (двоичный режим) — приводим к виду «хеш  имя», как в Linux
(cd "$dist" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum) |
  sed -E 's/^([0-9a-f]{64}) [ *]/\1  /' >"$manifest"
[[ -s "$manifest" ]] || { echo "pack: пустая сборка" >&2; exit 1; }
cp "$manifest" "$dist/MANIFEST.sha256"

rm -f "$out"
tar --force-local -C "$dist" --sort=name --owner=0 --group=0 --numeric-owner -czf "$out" .

files="$(grep -c '' "$dist/MANIFEST.sha256")"
size="$(stat -c %s "$out")"
echo "pack: $out — файлов $files, архив $size байт"
