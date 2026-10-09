#!/usr/bin/env bash
# Проверка сборки для боевого qodex.tech перед выкладкой.
#   deploy/ci/check-dist.sh <папка сборки> <номер версии>
# Собирает все найденные ошибки и в конце завершается с кодом 1, если они есть.
# Сборка должна быть сделана с SITE_URL=https://qodex.tech SITE_BASE=/ PUBLIC_FORM_ENDPOINT=/api/request
# PUBLIC_BUILD_ID=<номер версии> (так собирает .github/workflows/deploy-prod.yml).
set -euo pipefail
export LC_ALL=C

dist="${1:?нужна папка сборки}"
id="${2:?нужен номер версии}"
ORIGIN='https://qodex.tech'

# Страницы, которые должны быть открыты поисковикам, и их адреса
PAGES=(
  / /ro-bot/ /tracker/ /tonn/ /kodeks-tko/
  /documents/ /documents/ro-bot/ /documents/user_agreement/
  /privacy/ /consent/
)
# Файлы, ссылки на которые разосланы в письмах, реестрах и самих документах прежнего сайта (qodex.tech/files/…)
FILES=(
  gov.pdf gravity_manual.pdf partners_map.pdf policy.pdf requirements.pdf support.pdf system.pdf
  tonn_admin_guide.pdf tonn_functions.pdf tonn_lifecycle.pdf tonn_user_guide.pdf tracker.pdf user_agreement.pdf
)
# Скриншоты кабинета TONN: лендинг tonn.qodex.tech показывает их прямо с qodex.tech
# (<img src="https://qodex.tech/embed/…">, deploy/nginx/REDIRECTS.md) — без них картинки пропадут с лендинга
EMBEDS=(act.jpg analytica.jpg auto.jpg contragents.jpg)
# Пределы приёмника на сервере (deploy/server/qodex-release)
MAX_FILES=20000
MAX_BYTES=1073741824
NAME_RE='^[A-Za-z0-9._/@+=,~-]+$'

errors=0
err() {
  errors=$((errors + 1))
  if [[ "${GITHUB_ACTIONS:-}" == true ]]; then echo "::error::$*"; else echo "ОШИБКА: $*"; fi
}

# путь страницы → файл в сборке
page_file() {
  local p="${1#/}"
  if [[ -z "$p" || "$p" == */ ]]; then printf '%s/%sindex.html' "$dist" "$p"
  elif [[ -f "$dist/$p" ]]; then printf '%s/%s' "$dist" "$p"
  elif [[ -f "$dist/$p.html" ]]; then printf '%s/%s.html' "$dist" "$p"
  else printf '%s/%s/index.html' "$dist" "$p"
  fi
}

is_noindex() {
  grep -Eq '<meta name="robots" content="[^"]*noindex' "$1"
}

[[ -d "$dist" ]] || { err "нет папки сборки $dist"; exit 1; }

# --- обязательные файлы ---------------------------------------------------------------------------
for f in index.html 404.html robots.txt sitemap.xml; do
  [[ -f "$dist/$f" ]] || err "нет $f"
done
[[ ! -e "$dist/MANIFEST.sha256" ]] || err "MANIFEST.sha256 уже есть в сборке (его создаёт pack.sh)"
for f in "${FILES[@]}"; do
  [[ -f "$dist/files/$f" ]] || err "нет документа /files/$f"
done
for f in "${EMBEDS[@]}"; do
  [[ -s "$dist/embed/$f" ]] || err "нет картинки /embed/$f (её показывает лендинг tonn.qodex.tech)"
done

# --- главные страницы: открыты поисковикам, верный canonical, номер версии -------------------------
for p in "${PAGES[@]}"; do
  f="$(page_file "$p")"
  if [[ ! -f "$f" ]]; then err "нет страницы $p"; continue; fi
  if is_noindex "$f"; then err "страница $p закрыта от поисковиков (noindex)"; fi
  grep -Fq "<link rel=\"canonical\" href=\"$ORIGIN$p\">" "$f" || err "страница $p: canonical не $ORIGIN$p"
  grep -Fq "<meta name=\"qodex-build\" content=\"$id\">" "$f" || err "страница $p: нет <meta name=\"qodex-build\" content=\"$id\">"
done

# служебные страницы закрыты
while IFS= read -r f; do
  is_noindex "$f" || err "служебная страница ${f#"$dist"} не закрыта от поисковиков"
done < <(find "$dist/preview" -name '*.html' 2>/dev/null)

# --- следы сборки для GitHub Pages ----------------------------------------------------------------
leftovers="$(grep -rlE 'qodex_new_promo|kavabangaga\.github\.io' "$dist" \
  --include='*.html' --include='*.js' --include='*.css' --include='*.xml' --include='*.txt' \
  --include='*.json' --include='*.svg' --include='*.webmanifest' || true)"
[[ -z "$leftovers" ]] || err "адреса предварительной версии (GitHub Pages) в файлах: $(tr '\n' ' ' <<<"$leftovers")"

# --- форма заявки отправляет на приёмник ----------------------------------------------------------
grep -rqF '/api/request' "$dist" --include='*.html' --include='*.js' ||
  err "в сборке нет адреса формы /api/request (переменная PUBLIC_FORM_ENDPOINT не дошла до формы)"

# --- внутренние ссылки ведут на существующие файлы ------------------------------------------------
broken=''
while IFS= read -r p; do
  p="${p%%[?#]*}"
  [[ -n "$p" && "$p" != /api/* ]] || continue
  [[ -f "$(page_file "$p")" ]] || broken+="$p "
done < <(
  {
    grep -rhoE '(href|src)="/[^/"][^"]*"|(href|src)="/"' "$dist" --include='*.html' |
      sed -E 's/^(href|src)="//; s/"$//'
    grep -rhoE 'srcset="[^"]*"' "$dist" --include='*.html' |
      sed -E 's/^srcset="//; s/"$//' | tr ',' '\n' | awk '{ print $1 }' | grep '^/' || true
  } | sort -u
)
[[ -z "$broken" ]] || err "ссылки на несуществующие файлы: $broken"

# --- robots.txt и sitemap.xml ---------------------------------------------------------------------
if [[ -f "$dist/robots.txt" ]]; then
  grep -Fxq "Sitemap: $ORIGIN/sitemap.xml" "$dist/robots.txt" || err "robots.txt: нет строки Sitemap: $ORIGIN/sitemap.xml"
  if grep -Eq '^Disallow:[[:space:]]*/[[:space:]]*$' "$dist/robots.txt"; then err "robots.txt закрывает весь сайт"; fi
fi
if [[ -f "$dist/sitemap.xml" ]]; then
  mapfile -t locs < <(grep -oE '<loc>[^<]*</loc>' "$dist/sitemap.xml" | sed -E 's#</?loc>##g')
  (( ${#locs[@]} > 0 )) || err "sitemap.xml пуст"
  for loc in "${locs[@]}"; do
    if [[ "$loc" != "$ORIGIN"/* ]]; then err "sitemap.xml: чужой адрес $loc"; continue; fi
    p="${loc#"$ORIGIN"}"
    f="$(page_file "$p")"
    if [[ ! -f "$f" ]]; then err "sitemap.xml: нет страницы $p"
    elif is_noindex "$f"; then err "sitemap.xml: закрытая страница $p"
    fi
    if [[ "$p" == /preview/* || "$p" == /s/* || "$p" == /404* ]]; then err "sitemap.xml: служебная страница $p"; fi
  done
  for p in "${PAGES[@]}"; do
    printf '%s\n' "${locs[@]}" | grep -Fxq "$ORIGIN$p" || err "sitemap.xml: нет страницы $p"
  done
fi

# --- то, что примет приёмник на сервере -----------------------------------------------------------
special="$(find "$dist" -mindepth 1 ! -type f ! -type d -print | head -n 5)"
[[ -z "$special" ]] || err "символьные ссылки или особые файлы: $special"
badnames="$(cd "$dist" && find . -mindepth 1 | grep -Ev -- "$NAME_RE" | head -n 5 || true)"
[[ -z "$badnames" ]] || err "имена файлов вне латиницы, цифр и ._-/@+=,~ (приёмник их не примет): $badnames"
count="$(find "$dist" | wc -l)"
(( count <= MAX_FILES )) || err "файлов $count, приёмник примет не больше $MAX_FILES"
bytes="$(find "$dist" -type f -printf '%s\n' | awk '{ s += $1 } END { print s + 0 }')"
(( bytes <= MAX_BYTES )) || err "сборка $bytes байт, приёмник примет не больше $MAX_BYTES"

if (( errors > 0 )); then
  echo "check-dist: ошибок — $errors"
  exit 1
fi
echo "check-dist: сборка $id в порядке — файлов $count, $((bytes / 1024 / 1024)) МБ"
