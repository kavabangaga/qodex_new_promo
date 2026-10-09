# Переадресация адресов прежнего qodex.tech

Когда qodex.tech переключится на новый сайт, на адреса прежнего сайта (Nuxt, `/opt/qodex-promo`) продолжат вести поисковики, закладки, ссылки в письмах, PDF и на других сайтах. Чтобы такие ссылки не вели в пустоту, каждый старый адрес либо открывается как раньше, либо ведёт на ближайшую страницу нового сайта.

- Правила для nginx: [`qodex-site-redirects.conf`](qodex-site-redirects.conf). На сервере файл лежит в `/etc/nginx/snippets/qodex-site-redirects.conf` и подключается внутри `server { … }` сайта qodex.tech.
- Перенесённые файлы: `version4/public/embed/` (4 картинки), документы `version4/public/files/` уже были.
- Список старых адресов собран 2026-10-09: по папке прежнего сайта на сервере, по самим страницам и скриптам прежнего сайта, по журналу nginx (самые частые запросы) и по лендингам tonn, tracker, fgis и romoney.qodex.tech: какие адреса qodex.tech они используют.

## Страницы

Переход 301 (постоянный): поисковики переносят старый адрес в выдаче на новый. Метки из ссылки (`?utm_source=…`) сохраняются.

| Старый адрес | Новый адрес | Почему |
|---|---|---|
| `/` | `/` | Главная, адрес не изменился. |
| `/contacts`, `/contacts/` | `/#kontakty` | Прежняя страница «Контакты»: почта, телефон, Telegram, форма заявки. На новом сайте всё это в разделе «Заявка» в конце главной. Реквизиты компании — в подвале и на странице «Документы». |
| `/project`, `/project/` | `/tonn/` | Страница «Проект» рассказывала о системе QODEX TONN, её модулях Gravity и Signall и результатах для регионального оператора. Сейчас это страница QODEX TONN. |
| `/demo-gravity`, `/demo-gravity/` | `/tonn/` | Gravity — часть QODEX TONN, которая работает на весовой: весы, распознавание номеров, камеры, шлагбаумы. Отдельной страницы у Gravity больше нет, о ней рассказывает страница QODEX TONN целиком. |
| `/demo-signall`, `/demo-signall/` | `/tonn/#kabinet` | Signall — веб-кабинет QODEX TONN: аналитика, акты, контрагенты, транспорт. На странице QODEX TONN это раздел «Кабинет. Возможности системы» с теми же экранами. |
| `/solution-embed.html` | `/tonn/#oborudovanie` | Встраиваемый блок «Решения для весовой» со схемой оборудования. На странице QODEX TONN есть тот же блок: «Как устроена ваша весовая с решениями QODEX». |
| `/_index`, `/_index/`, `/200.html` | `/` | Служебные копии главной, которые создавал Nuxt. |
| `/documents` | `/documents/` | Страница «Документы» есть и на новом сайте, её основной адрес с косой чертой в конце. Этот адрес проверяет Минцифры, поэтому переход прописан явно и не зависит от других настроек nginx. Адрес `/documents/` открывается напрямую. |

## Данные страниц Nuxt: ответ 410

`/_payload.json`, `/_index/_payload.json`, `/contacts/_payload.json`, `/documents/_payload.json`, `/project/_payload.json`, `/demo-gravity/_payload.json`, `/demo-signall/_payload.json`, в том числе с любым `?…` после адреса.

Это не страницы, а данные в формате JSON, которые подгружал скрипт прежнего сайта. Их по-прежнему запрашивают роботы, по журналу сотни раз. Переход на HTML-страницу сломал бы разбор JSON, поэтому сервер отвечает 410 «адреса больше нет», и роботы со временем перестают его запрашивать.

## Файлы

| Старый адрес | Что с ним | Почему |
|---|---|---|
| `/files/gov.pdf`, `gravity_manual.pdf`, `partners_map.pdf`, `requirements.pdf`, `support.pdf`, `system.pdf`, `tonn_admin_guide.pdf`, `tonn_functions.pdf`, `tonn_lifecycle.pdf`, `tonn_user_guide.pdf`, `tracker.pdf`, `user_agreement.pdf` | Открываются по тем же адресам | Лежат в `version4/public/files/` под прежними именами и побайтно совпадают со старыми (SHA-256 сверены 2026-10-09). На `policy.pdf` и `user_agreement.pdf` ссылаются лендинги tonn, tracker и fgis.qodex.tech. |
| `/files/policy.pdf` | Открывается по тому же адресу | На этом адресе новая редакция политики (2026-10-06). Ссылки лендингов на `qodex.tech/files/policy.pdf` продолжают работать. |
| `/files/partners_map (1).pdf` | 301 → `/files/partners_map.pdf` | Случайная копия: побайтно совпадает с `partners_map.pdf`. Правило срабатывает и для `%20`, и для `%28 %29` в адресе. |
| `/images/system.pdf` | 301 → `/files/system.pdf` | Та же презентация «О системе», побайтно. |
| `/embed/act.jpg`, `analytica.jpg`, `auto.jpg`, `contragents.jpg` | Открываются по тем же адресам | Это скриншоты кабинета QODEX TONN (акты, аналитика, транспорт, контрагенты). Лендинг tonn.qodex.tech показывает их прямо с qodex.tech, через `<img src="https://qodex.tech/embed/…">`. Файлы скопированы в `version4/public/embed/` без изменений, размеры совпадают. Без них картинки пропали бы с лендинга. |
| `/favicon.png` | 301 → `/favicon.ico` | Значок прежнего сайта. У нового сайта значки `favicon.ico`, `favicon.svg` и `apple-touch-icon.png`. |
| `/_nuxt/…`, `/fonts/…`, `/images/…` (кроме `system.pdf`), `/videos/…`, `/contacts/index.html` и т. п. | 404 | Это оформление прежнего сайта: скрипты, шрифты, картинки, фоновое видео. Новый сайт их не использует. Внешних ссылок на них не нашлось, лендинги ссылаются только на `/embed/` и `/files/`. `/videos/presentation.mp4` — 70-секундная запись экрана телефона 2024 года, ни одна страница прежнего сайта на неё не ссылалась. |

Сам переход с `www.qodex.tech` на `qodex.tech` и с http на https задан в описании сайта (`qodex.tech.conf`), а не в этом файле.

## Что ещё выяснилось

- **Блок на лендинге TONN уже не работает, и наш переход тут ни при чём.** Блок «Как устроена ваша весовая» на tonn.qodex.tech встраивает `https://test.qodex.tech/solution-embed.html`, а не адрес qodex.tech. Сертификат на test.qodex.tech не выпущен: браузер отказывается открывать страницу, а без проверки сертификата сервер отвечает 404. Поэтому блок на лендинге сейчас пустой. Вопрос снимется, когда сам лендинг начнёт переадресовывать на `/tonn/` (это запланировано).
- **Неизвестные адреса.** Прежний сайт на любой неизвестный адрес, включая `/robots.txt` и `/sitemap.xml`, отдавал главную страницу с ответом 200. Новый сайт отвечает 404 и показывает свою страницу 404.
- **Свои страницы-переходы нового сайта** остаются как есть, в nginx они не продублированы. Это `/requirements/`, `/documents/requirements/`, `/documents/support/`, `/documents/manuals/`: адреса, которые напечатаны внутри PDF.

## Как проверяли

На этом компьютере запустили nginx 1.22.1 той же версии, что на сервере. Сайт был собран из `version4`, правила подключены в двух вариантах описания сайта: `try_files $uri $uri/ =404` и `try_files $uri $uri/index.html $uri.html =404`. Результат одинаковый в обоих вариантах:

- `nginx -t` — ошибок нет;
- все 28 старых адресов отвечают нужным кодом и адресом, адрес назначения открывается с ответом 200, а якорь (`#kontakty`, `#kabinet`, `#oborudovanie`) на странице есть;
- ни один из 252 адресов нового сайта (все файлы сборки и страницы без `index.html`) правилами не перекрыт, все отвечают 200;
- `/embed/*.jpg` отдаются побайтно такими же, как на старом сайте; ресурсы, которые не переносим, отвечают 404.

## Проверка на боевом сервере после переключения

Команда для Git Bash или сервера, нужен curl 7.84 или новее. Без переменных проверяет https://qodex.tech. До переключения DNS-записи можно проверить сервер напрямую: `CURL_OPTS="--resolve qodex.tech:443:82.146.59.244"`.

```bash
BASE=${BASE:-https://qodex.tech}
while read -r path want; do
  got=$(curl -s $CURL_OPTS -o /dev/null -w '%{http_code} %header{location}' "$BASE$path")
  got=${got% }
  [ "$got" = "$want" ] && echo "OK      $path" || echo "ОШИБКА  $path: «$got», ждали «$want»"
done <<'EOF'
/contacts 301 https://qodex.tech/#kontakty
/contacts/ 301 https://qodex.tech/#kontakty
/project 301 https://qodex.tech/tonn/
/project/ 301 https://qodex.tech/tonn/
/demo-gravity 301 https://qodex.tech/tonn/
/demo-gravity/ 301 https://qodex.tech/tonn/
/demo-signall 301 https://qodex.tech/tonn/#kabinet
/demo-signall/ 301 https://qodex.tech/tonn/#kabinet
/_index 301 https://qodex.tech/
/_index/ 301 https://qodex.tech/
/200.html 301 https://qodex.tech/
/solution-embed.html 301 https://qodex.tech/tonn/#oborudovanie
/documents 301 https://qodex.tech/documents/
/documents/ 200
/_payload.json 410
/documents/_payload.json 410
/files/partners_map%20(1).pdf 301 https://qodex.tech/files/partners_map.pdf
/images/system.pdf 301 https://qodex.tech/files/system.pdf
/favicon.png 301 https://qodex.tech/favicon.ico
/files/policy.pdf 200
/files/user_agreement.pdf 200
/embed/act.jpg 200
/embed/analytica.jpg 200
/embed/auto.jpg 200
/embed/contragents.jpg 200
EOF
```

## Как добавить правило

Только точное совпадение, полный адрес назначения и метки из ссылки:

```nginx
location = /старый-адрес  { return 301 https://qodex.tech/новый-адрес/$is_args$args; }
location = /старый-адрес/ { return 301 https://qodex.tech/новый-адрес/$is_args$args; }
```

Якорь пишется после `$is_args$args`: `…/tonn/$is_args$args#kabinet`. Адрес с пробелом берётся в кавычки: `location = "/files/имя (1).pdf"`. Перед добавлением проверьте, что в сборке нового сайта (`version4/dist`) нет файла или страницы с таким путём, иначе правило её перекроет. После правки на сервере: `sudo nginx -t`, затем `sudo systemctl reload nginx`.
