#!/usr/bin/env bash
# Проверка боевого сайта снаружи после выкладки или отката.
#   deploy/ci/smoke.sh <номер версии, которая должна быть на сайте>
# Номер версии сайт показывает в <meta name="qodex-build" content="…"> (layouts/Base.astro).
#
# SMOKE_REQUIRE_BUILD=1 (переменная репозитория, ставится после переключения nginx на /opt/qodex-site,
# deploy/README.md): прежний сайт на qodex.tech — уже ошибка. Без неё прежний сайт (Nuxt, его узнаём
# по /_nuxt/ в странице) значит «nginx ещё не переключён»: выкладка прошла, проверять нечего.
#
# Код выхода:
#   0 — на сайте эта версия и всё в порядке; или на qodex.tech ещё прежний сайт, а SMOKE_REQUIRE_BUILD не 1;
#   3 — сайт показывает не ту версию или страницы этой версии не открываются (404 и т. п.) — откат поможет;
#   4 — настройки nginx не те (www, http, /api, заголовки, тип PDF, прежний сайт после переключения,
#       чужая страница без номера версии) — откат не поможет;
#   5 — сервер не отвечает или отвечает 5xx — откат не поможет (и результаты остальных проверок
#       тогда ненадёжны, поэтому 5 важнее 3).
set -euo pipefail
export LC_ALL=C

id="${1:?нужен номер версии}"
ORIGIN="${SITE_ORIGIN:-https://qodex.tech}"
HOST="${ORIGIN#https://}"
WAIT="${SMOKE_WAIT:-60}"
REQUIRE_BUILD="${SMOKE_REQUIRE_BUILD:-}"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

gh() { [[ "${GITHUB_ACTIONS:-}" == true ]]; }
notice() { if gh; then echo "::notice::$*"; else echo "ВНИМАНИЕ: $*"; fi; }
error() { if gh; then echo "::error::$*"; else echo "ОШИБКА: $*"; fi; }
passed() { echo "  ok  $*"; }

# fetch <адрес> — печатает код ответа (000 — нет связи); тело в $tmp/body, заголовки в $tmp/headers
fetch() {
  curl -sS --max-time 20 -H 'Cache-Control: no-cache' \
    -o "$tmp/body" -D "$tmp/headers" -w '%{http_code}' "$1" 2>"$tmp/curl.err" || true
}
# redirect_of <адрес> — «код адрес-перехода»
redirect_of() {
  curl -sS --max-time 20 -o /dev/null -w '%{http_code} %{redirect_url}' "$1" 2>/dev/null || true
}
header() {
  grep -i "^$1:" "$tmp/headers" | tail -n 1 | cut -d: -f2- | tr -d '\r' | sed -E 's/^ +//' || true
}
build_of() {
  sed -nE 's/.*<meta name="qodex-build" content="([^"]*)".*/\1/p' "$tmp/body" | head -n 1
}
# нет связи (000) или 5xx — беда сервера, а не версии
server_code() {
  [[ "$1" == 000 || "$1" == 5* ]]
}

# --- 1. какая версия на сайте ---------------------------------------------------------------------
deadline=$((SECONDS + WAIT))
while :; do
  code="$(fetch "$ORIGIN/")"
  served=''
  if [[ "$code" == 200 ]]; then
    served="$(build_of)"
    [[ "$served" != "$id" ]] || break
    if [[ -z "$served" ]] && grep -q '/_nuxt/' "$tmp/body"; then
      if [[ "$REQUIRE_BUILD" != 1 ]]; then
        notice "На $ORIGIN/ ещё прежний сайт (Nuxt): nginx не переключён на /opt/qodex-site. Версия $id лежит на сервере и станет видна после переключения (deploy/README.md)."
        exit 0
      fi
      error "На $ORIGIN/ прежний сайт (Nuxt), а nginx уже переключали на новый (переменная SMOKE_REQUIRE_BUILD=1): вернулись прежние настройки nginx? Откат версии не поможет (deploy/README.md)."
      exit 4
    fi
  fi
  if (( SECONDS >= deadline )); then
    if [[ "$code" == 000 ]]; then error "$ORIGIN/ не отвечает: $(head -c 300 "$tmp/curl.err")"; exit 5; fi
    if server_code "$code"; then error "$ORIGIN/ отвечает $code"; exit 5; fi
    if [[ "$code" != 200 ]]; then error "$ORIGIN/ отвечает $code — настройки nginx?"; exit 4; fi
    if [[ -z "$served" ]]; then
      error "$ORIGIN/ отдаёт страницу без <meta name=\"qodex-build\">, и это не прежний сайт — настройки nginx?"
      exit 4
    fi
    error "на сайте версия $served, а должна быть $id"
    exit 3
  fi
  sleep 5
done
passed "на $ORIGIN/ версия $id"

content_fail=0
config_fail=0
server_fail=0
bad_content() { error "$*"; content_fail=1; }
bad_config() { error "$*"; config_fail=1; }
bad_server() { error "$*"; server_fail=1; }

# главная открыта поисковикам, страницы не кэшируются надолго, заголовки безопасности на месте
if grep -Eq '<meta name="robots" content="[^"]*noindex' "$tmp/body"; then bad_content "главная закрыта от поисковиков (noindex)"; fi
[[ "$(header Cache-Control)" == no-cache ]] || bad_config "/: Cache-Control «$(header Cache-Control)», нужно no-cache"
[[ "$(header X-Content-Type-Options)" == nosniff ]] || bad_config "/: нет X-Content-Type-Options: nosniff"
[[ -n "$(header Referrer-Policy)" ]] || bad_config "/: нет Referrer-Policy"
asset="$(grep -oE '/_astro/[A-Za-z0-9._@+=,~-]+\.(css|js)' "$tmp/body" | head -n 1 || true)"

# --- 2. страницы и файлы этой версии (ошибка — откат; 5xx и нет связи — нет) -----------------------
for p in /ro-bot/ /tracker/ /tonn/ /kodeks-tko/ /documents/ /privacy/; do
  code="$(fetch "$ORIGIN$p")"
  if server_code "$code"; then bad_server "$p отвечает $code"
  elif [[ "$code" != 200 ]]; then bad_content "$p отвечает $code"
  elif [[ "$(build_of)" != "$id" ]]; then bad_content "$p: версия «$(build_of)», а не $id"
  else passed "$p"
  fi
done
code="$(fetch "$ORIGIN/files/requirements.pdf")"
if server_code "$code"; then bad_server "/files/requirements.pdf отвечает $code"
elif [[ "$code" != 200 ]]; then bad_content "/files/requirements.pdf отвечает $code"
elif [[ "$(header Content-Type)" != application/pdf* ]]; then
  bad_config "/files/requirements.pdf: Content-Type «$(header Content-Type)», нужно application/pdf (mime.types nginx)"
else passed "/files/requirements.pdf"
fi
code="$(fetch "$ORIGIN/robots.txt")"
if server_code "$code"; then bad_server "/robots.txt отвечает $code"
elif [[ "$code" == 200 ]] && grep -Fq "Sitemap: $ORIGIN/sitemap.xml" "$tmp/body"; then passed "/robots.txt"
else bad_content "/robots.txt: $code или нет строки Sitemap"
fi
code="$(fetch "$ORIGIN/sitemap.xml")"
if server_code "$code"; then bad_server "/sitemap.xml отвечает $code"
elif [[ "$code" == 200 ]] && grep -Fq "<loc>$ORIGIN/</loc>" "$tmp/body"; then passed "/sitemap.xml"
else bad_content "/sitemap.xml: $code или нет главной"
fi
if [[ -n "$asset" ]]; then
  code="$(fetch "$ORIGIN$asset")"
  if server_code "$code"; then bad_server "$asset отвечает $code"
  elif [[ "$code" != 200 ]]; then bad_content "$asset отвечает $code"
  elif [[ "$(header Cache-Control)" != *immutable* ]]; then bad_config "$asset: Cache-Control «$(header Cache-Control)», нужно immutable"
  else passed "$asset"
  fi
fi
code="$(fetch "$ORIGIN/net-takoy-stranicy-$id/")"
if server_code "$code"; then bad_server "несуществующий адрес: $code"
elif [[ "$code" != 404 ]]; then bad_config "несуществующий адрес: $code, нужно 404"
elif [[ "$(build_of)" != "$id" ]]; then bad_content "несуществующий адрес: страница 404 версии «$(build_of)», а не $id"
else passed "несуществующий адрес → 404 с нашей страницей"
fi

# --- 3. настройки nginx (ошибка — без отката) -----------------------------------------------------
expect_redirect() {
  local url="$1" want="$2" got
  got="$(redirect_of "$url")"
  if [[ "$got" == "301 $want" ]]; then passed "$url → $want"
  elif server_code "${got%% *}"; then bad_server "$url: «$got»"
  else bad_config "$url: «$got», нужно 301 → $want"
  fi
}
expect_redirect "https://www.$HOST/" "$ORIGIN/"
expect_redirect "https://www.$HOST/ro-bot/?utm_source=smoke" "$ORIGIN/ro-bot/?utm_source=smoke"
expect_redirect "http://www.$HOST/" "$ORIGIN/"
expect_redirect "http://$HOST/tonn/" "$ORIGIN/tonn/"

expect_code() {
  local url="$1" want="$2" got
  got="$(fetch "$url")"
  if [[ "$got" == "$want" ]]; then passed "$url → $want"
  elif server_code "$got"; then bad_server "$url: $got, нужно $want"
  else bad_config "$url: $got, нужно $want"
  fi
}
expect_code "$ORIGIN/api/docs" 404
expect_code "$ORIGIN/api/openapi.json" 404
expect_code "$ORIGIN/api/request" 403
expect_code "$ORIGIN/.env" 404
expect_code "$ORIGIN/MANIFEST.sha256" 404
expect_code "$ORIGIN/404.html" 404
expect_code "$ORIGIN/404" 404
expect_code "$ORIGIN/contacts" 301

if (( server_fail )); then exit 5; fi
if (( content_fail )); then exit 3; fi
if (( config_fail )); then exit 4; fi
echo "smoke: версия $id на $ORIGIN, проверки пройдены"
