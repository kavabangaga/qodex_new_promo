# Выкладка сайта qodex.tech

Как новый сайт попадает на боевой сервер, как откатить версию и что настроено на сервере.
Для заказчика и для Евгения.

## Цепочка

```
разработчик ──► ветка dev ──► GitHub Actions: сборка и проверки (без выкладки)
                    │
                    └──► kavabangaga/qodex_new_promo (main) ──► GitHub Pages: предварительная версия
                                                              https://kavabangaga.github.io/qodex_new_promo/v4/

«на бой» ──► ветка main ──► GitHub Actions: сборка ─► проверки ─► архив ─► ssh ─► сервер 82.146.59.244
                                                                                    │
             проверка https://qodex.tech снаружи ◄──── переключение версии ◄───────┘
             (не та версия на сайте → автоматический откат)
```

- Код сайта — рабочий репозиторий **SIGNALL-D/qodex-site** (приватный), папка `version4/`.
- **dev** — черновики. Каждая отправка собирается и проверяется, на боевой сайт не попадает.
  Предварительную версию показывает GitHub Pages личного репозитория kavabangaga/qodex_new_promo:
  туда отправляется состояние dev (в его ветку main). Предварительная версия закрыта от поисковиков,
  форма заявки там письма не отправляет.
- **main** — боевой сайт. Правка попадает в main, когда заказчик говорит «на бой»: dev сливается в main.
  Через 3–5 минут она на https://qodex.tech.
- Выкладку делает `.github/workflows/deploy-prod.yml` («Выкладка на боевой» во вкладке Actions).
  Предварительную версию — `.github/workflows/deploy.yml`. Каждый файл работает только в своём репозитории.

### Что происходит при отправке в main

1. Сборка `version4` для qodex.tech (адрес формы — `/api/request`, номер версии — в каждой странице).
2. Проверка сборки (`deploy/ci/check-dist.sh`): главные страницы открыты поисковикам, документы на месте,
   все ссылки внутри сайта ведут на существующие файлы, нет адресов предварительной версии, есть
   `sitemap.xml` и `robots.txt`, форма отправляет на `/api/request`.
3. Проверка приёмника на сервере (`deploy/server/test-qodex-release.sh`) — на копии, без сервера.
4. Архив сайта со списком контрольных сумм всех файлов (`deploy/ci/pack.sh`).
5. Выкладка сверяется с GitHub: если её коммит уже не последний в main (пока она собиралась, пришла
   правка новее), она пропускается — задание зелёное, с пометкой «Пропущено». Последний коммит выложит
   своя выкладка.
6. Архив уходит по ssh на сервер (`deploy/ci/deploy.sh`). Ключ выкладки может запустить там только одну
   программу — приёмник `/opt/qodex-site/bin/qodex-release`. Приёмник проверяет архив (только обычные
   файлы и папки с обычными правами, безопасные имена, контрольные суммы, есть `index.html` и `404.html`),
   раскладывает его в новую папку и одной операцией переключает сайт на неё. Посетители видят либо
   прежнюю версию, либо новую целиком. Версию старше той, что сейчас на сайте, приёмник не принимает.
7. Проверка https://qodex.tech снаружи (`deploy/ci/smoke.sh`): на сайте именно эта версия, страницы
   продуктов, документы, `robots.txt`, `sitemap.xml`, страница 404, переадресация с www и http,
   закрытые `/api/docs` и `/.env`. Если сайт показывает не ту версию или её страницы не открываются —
   автоматически возвращается предыдущая версия, а задание завершается ошибкой. Если сервер не отвечает
   или отвечает 5xx, или не те настройки nginx (заголовки, переадресации, тип PDF) — задание
   завершается ошибкой **без отката**: прежняя версия тут не поможет, нужен человек.

Номер версии: `ГГГГММДД-ЧЧММСС-коммит`, где время — **время коммита** по UTC (не сборки), например
`20261009-121500-cb1061a`. Он виден в коде любой страницы: `<meta name="qodex-build" content="…">`.
Повторный запуск того же коммита даёт тот же номер.

Если в main отправить несколько правок подряд, их сборки идут одновременно, а выкладки — по одной, в
очереди (`queue: max`: ожидающие выкладки GitHub не отменяет, и откат из Actions их тоже не отменяет).
Сборка старой правки может закончиться позже новой — тогда её выкладка пропускается (шаг 5), а если
она всё же дошла до сервера, приёмник откажет («версия … старше текущей»). На сайт попадает последнее
состояние main.

**Повторный запуск** (Actions → задание → Re-run failed jobs, например после автоматического отката или
обрыва связи): если версия уже лежит на сервере, выкладка не загружает её заново, а переключает сайт
на неё (в журнале задания: «Версия … уже лежит на сервере (повторный запуск) — переключаю сайт на неё»).

## Откат

**Обычный откат — одна кнопка, около минуты:**

1. GitHub → SIGNALL-D/qodex-site → **Actions** → «Выкладка на боевой» → **Run workflow**.
2. Use workflow from: **main**, action: **rollback**, поле «Номер версии» оставить пустым → **Run workflow**.

Вернётся версия, которая была на сайте до последнего переключения. Повторный rollback вернёт обратно
(как «отменить»). После отката задание само проверяет qodex.tech.

**Откат на конкретную версию:** сначала action **status** — в итоге задания таблица версий на сервере
и какую видят посетители. Затем **rollback** с номером версии из таблицы. На сервере хранятся
5 последних версий, а также текущая и предыдущая, даже если они старше.

**Важно:** откат меняет только то, что показывает сервер. Код в main остаётся прежним, и следующая
выкладка вернёт ошибку. Поэтому после отката исправьте main (или отмените коммит: `git revert`).
Вернуть старое состояние перезаписью main старым коммитом (`git reset` + `push --force`) не выйдет:
версию старше той, что на сайте, сервер не примет. Для этого есть rollback, а для кода — `git revert`
(новый коммит с прежним содержимым).

`status` и `rollback` ждут, пока закончится идущая выкладка (до 2 минут), и только потом отвечают.
Ответ «занято» — выкладка ещё идёт, повторите через минуту.

**Без GitHub** (GitHub недоступен) — на сервере, под администратором:

```bash
sudo -u qodex /opt/qodex-site/bin/qodex-release status
sudo -u qodex /opt/qodex-site/bin/qodex-release rollback
sudo -u qodex /opt/qodex-site/bin/qodex-release rollback 20261009-121500-cb1061a
```

**Вернуть прежний сайт целиком** (Nuxt, `/opt/qodex-promo` — он остаётся на сервере): вернуть копию
прежних настроек nginx, см. «Возврат на прежний сайт» ниже.

## Сервер

Debian 12, nginx 1.22, на сервере живут и другие сайты (about, ms, romoney.qodex.tech и др.).

```
/opt/qodex-site/                      владелец qodex
├── bin/qodex-release                 приёмник выкладки (из deploy/server/qodex-release), владелец root
├── releases/<версия>/                по папке на выкладку
├── upload/                           архив, пока он принимается и проверяется (потом удаляется)
├── current -> releases/<версия>      то, что показывает nginx
├── previous                          номер версии, бывшей на сайте до последнего переключения
├── log/deploy.log                    журнал: выкладки, откаты, отказы, с адресом и временем
└── .lock                             замок: две выкладки одновременно не идут

/etc/nginx/sites-enabled/qodex.tech             ← deploy/nginx/qodex.tech.conf
/etc/nginx/snippets/qodex-site-headers.conf     ← deploy/nginx/qodex-site-headers.conf
/etc/nginx/snippets/qodex-site-redirects.conf   ← deploy/nginx/qodex-site-redirects.conf (таблица — deploy/nginx/REDIRECTS.md)
/etc/nginx/conf.d/qodex-site-limits.conf        ← deploy/nginx/qodex-site-limits.conf
/etc/nginx/qodex-backup/                        копии прежних настроек nginx
/home/qodex/.ssh/authorized_keys                строка ключа выкладки (restrict,command=…)
```

Что настроено в nginx (`deploy/nginx/qodex.tech.conf`):

- главный адрес — `https://qodex.tech`; `www.qodex.tech` и `http://` переадресуются на него (301);
- адреса прежнего сайта (`/contacts`, `/project`, `/demo-gravity`, старые картинки и т. п.) — 301
  на ближайшие страницы нового сайта (`qodex-site-redirects.conf`);
- **заявки с формы:** `POST /api/request` → прежний отправщик писем (служба `mail.service`,
  `/opt/mail-sender`, 127.0.0.1:9012) → письмо с no-reply@qodex.tech на info@qodex.tech. Только POST
  (GET и прочее — 403), тело до 16 КБ. Частота с одного адреса: подряд проходят 6 заявок, седьмая сразу
  получает 429, дальше — одна в 10 секунд (за первую минуту около 11, потом 6 в минуту). Остальное
  под `/api/` (в том числе описание отправщика `/api/docs`) закрыто — 404;
- **копия заявки в CRM Weeek:** nginx повторяет каждый принятый `POST /api/request` (тот же JSON)
  на мост `server/weeek-bridge` (служба `qodex-weeek-bridge`, 127.0.0.1:9031, `POST /lead`), мост
  создаёт карточку. Ответ моста посетитель не ждёт: если мост выключен или молчит, заявка всё равно
  уходит письмом, а в `/var/log/nginx/error.log` появляется строка про `/_qodex_weeek`. Отказы
  (429, 403, слишком большое тело) в мост не попадают;
- кэш: файлы сборки `/_astro/` — год (в имени хеш), картинки `/media/` и `/clients/` — 30 дней,
  страницы и документы `/files/` — «каждый раз спросить сервер» (после выкладки видна новая версия);
- скрытые файлы (`/.env`, `/.git/…`) — 404; заголовки безопасности на всех ответах.

## Первичная установка (один раз)

Команды — для администратора сервера (пользователь с sudo). Файлы берутся из папки `deploy/`
репозитория. Сначала на сервере — своя временная папка (её создаёт `mktemp -d`, права только у вас; не
готовое имя вроде `/tmp/qodex-site-install`: такую папку мог заранее создать кто-то другой и подложить
в неё свои файлы):

```bash
D="$(mktemp -d)" && echo "$D"            # например /tmp/tmp.Kx3vQ9aB1c — нужна дальше
```

С компьютера разработчика — папка `deploy` туда (вместо `/tmp/tmp.Kx3vQ9aB1c` — то, что напечатал `echo`):

```bash
scp -r deploy qodex@82.146.59.244:/tmp/tmp.Kx3vQ9aB1c/
```

Дальше — на сервере, в той же сессии (переменная `D` нужна в шагах 1 и 5). В конце установки:
`rm -rf "$D"`.

### 1. Папки и приёмник

```bash
cd "$D/deploy"
sudo install -d -o qodex -g qodex -m 755 /opt/qodex-site /opt/qodex-site/releases /opt/qodex-site/log
sudo install -d -o root -g root -m 755 /opt/qodex-site/bin
sudo install -o root -g root -m 755 server/qodex-release /opt/qodex-site/bin/qodex-release
sudo -u qodex /opt/qodex-site/bin/qodex-release status     # ждём «current -» и «OK status»
```

Приёмник принадлежит root: ключ выкладки работает от имени qodex и не может его подменить.

### 2. Ключ выкладки

Отдельный ключ только для GitHub Actions. Создаётся на компьютере разработчика и хранится вне репозитория
(папка `.secrets`):

```bash
ssh-keygen -t ed25519 -N "" -C "github-actions qodex-site deploy" -f qodex-site-deploy
```

На сервере — копия `authorized_keys` и строка ключа **с ограничениями** (вместо `AAAA…` — содержимое
`qodex-site-deploy.pub` после `ssh-ed25519 `):

```bash
sudo cp -a /home/qodex/.ssh/authorized_keys /home/qodex/.ssh/authorized_keys.bak-$(date +%Y%m%d-%H%M%S)
echo 'restrict,command="/opt/qodex-site/bin/qodex-release" ssh-ed25519 AAAA… github-actions qodex-site deploy' \
  | sudo -u qodex tee -a /home/qodex/.ssh/authorized_keys >/dev/null
```

`restrict,command=…` — главное: с ним ключ может только запустить приёмник (выложить, откатить,
показать версии) и не даёт входа на сервер, терминала и проброса портов. Без этих слов ключ из GitHub
дал бы полный вход, а у qodex sudo без пароля.

Проверка с компьютера разработчика:

```bash
ssh -i qodex-site-deploy qodex@82.146.59.244 status   # «OK status»
ssh -i qodex-site-deploy qodex@82.146.59.244 id       # «ERR command: неизвестная команда» — так и надо
```

### 3. Настройки репозитория SIGNALL-D/qodex-site на GitHub

1. **Settings → Environments → New environment** → `production`.
   - Deployment branches and tags → **Selected branches and tags** → добавить `main`.
     Тогда ключ выкладки получают только задания из ветки main: workflow, изменённый в другой ветке,
     его не прочитает.
   - По желанию — **Required reviewers**: тогда каждая выкладка ждёт кнопки «Approve».
2. В окружении `production` → **Environment secrets**:
   - `DEPLOY_SSH_KEY` — всё содержимое файла `qodex-site-deploy` (закрытый ключ, вместе со строками
     `-----BEGIN…` и `-----END…`);
   - `DEPLOY_KNOWN_HOSTS` — строка отпечатка сервера:
     ```bash
     ssh-keyscan -t ed25519 82.146.59.244 > known_hosts.qodex
     ssh-keygen -lf known_hosts.qodex   # должно быть SHA256:IourIE1L7Hffz5ZzsN8GMYmQ7PIh29fsCkpGg9O/iiQ
     ```
     Если отпечаток другой — не продолжать, выяснить почему (его сняли с самого сервера 09.10.2026).
     В секрет — содержимое `known_hosts.qodex` (строка `82.146.59.244 ssh-ed25519 AAAA…`).
3. В окружении `production` → **Environment variables**: `DEPLOY_HOST` = `82.146.59.244`,
   `DEPLOY_USER` = `qodex`.
4. По желанию — Settings → Branches: защитить `main` от удаления и принудительной перезаписи.

### 4. Первая выкладка

Отправить код в main. В Actions задание «Выкладка на qodex.tech» положит версию на сервер и напишет
«На https://qodex.tech/ ещё прежний сайт… nginx не переключён» — так и должно быть до шага 5.

```bash
sudo -u qodex /opt/qodex-site/bin/qodex-release status    # current <версия>
ls /opt/qodex-site/current/                                # index.html, 404.html, _astro, files…
```

### 5. Переключение qodex.tech на новый сайт

```bash
cd "$D/deploy/nginx"
TS=$(date +%Y%m%d-%H%M%S)
sudo install -d -m 755 /etc/nginx/qodex-backup
sudo cp -a /etc/nginx/sites-enabled/qodex.tech /etc/nginx/qodex-backup/qodex.tech.$TS
sudo install -o root -g root -m 644 qodex-site-limits.conf    /etc/nginx/conf.d/qodex-site-limits.conf
sudo install -o root -g root -m 644 qodex-site-headers.conf   /etc/nginx/snippets/qodex-site-headers.conf
sudo install -o root -g root -m 644 qodex-site-redirects.conf /etc/nginx/snippets/qodex-site-redirects.conf
sudo install -o root -g root -m 644 qodex.tech.conf           /etc/nginx/sites-enabled/qodex.tech
sudo nginx -t && sudo systemctl reload nginx
```

- Копии — только в `/etc/nginx/qodex-backup/`, **не** в `sites-enabled`: nginx читает оттуда все файлы подряд,
  и копия заработала бы вместе с новым файлом.
- **Только `reload`, никогда `restart`**: reload подхватывает настройки без обрыва соединений, а при ошибке
  nginx продолжает работать на прежних. На сервере живут и другие сайты.
- Если `nginx -t` сообщил об ошибке — reload не выполнится (сайт работает по-старому). Вернуть копию:
  `sudo cp -a /etc/nginx/qodex-backup/qodex.tech.$TS /etc/nginx/sites-enabled/qodex.tech && sudo nginx -t`.
  Три новых файла в `conf.d` и `snippets` без нового `qodex.tech` ничему не мешают.

Проверка:

```bash
curl -s https://qodex.tech/ | grep -o '<meta name="qodex-build"[^>]*>'   # номер версии
curl -sI https://www.qodex.tech/ro-bot/ | grep -i '^location'            # https://qodex.tech/ro-bot/
curl -sI https://qodex.tech/contacts | grep -i '^location'                # https://qodex.tech/#kontakty
```

Затем в GitHub: Settings → Secrets and variables → Actions → **Variables** → New repository variable
`SMOKE_REQUIRE_BUILD` = `1`. С ней проверка после выкладки считает прежний сайт на qodex.tech ошибкой
(до переключения прежний сайт значит «nginx ещё не переключён», и выкладка зелёная). Если пришлось
вернуться на прежний сайт (ниже) — удалить переменную.

Полную проверку делает GitHub: Actions → «Выкладка на боевой» → Run workflow → main → **deploy**
(соберёт и выложит main заново и проверит сайт целиком). Затем — отправить заявку с формы на сайте
и убедиться, что письмо пришло на info@qodex.tech, а в Weeek появилась карточка (если мост
`qodex-weeek-bridge` уже установлен — `server/weeek-bridge/README.md`).

Сертификат продлевает certbot (qodex.tech и www.qodex.tech). Убедиться, что продление работает
с новыми настройками:

```bash
sudo certbot renew --dry-run --cert-name qodex.tech
```

### Возврат на прежний сайт

```bash
ls /etc/nginx/qodex-backup/                     # выбрать копию
sudo cp -a /etc/nginx/qodex-backup/qodex.tech.<время> /etc/nginx/sites-enabled/qodex.tech
sudo nginx -t && sudo systemctl reload nginx
```

Прежний сайт в `/opt/qodex-promo` и его отправщик писем не тронуты. Выкладки нового сайта при этом
продолжают ложиться в `/opt/qodex-site`, но посетители их не видят. Переменную `SMOKE_REQUIRE_BUILD`
в GitHub удалить — иначе каждая выкладка будет красной («прежний сайт»).

## Что не трогать

- **Папки `/opt/qodex-site/releases/` и ссылку `current` руками не править.** Правка мимо репозитория
  пропадёт со следующей выкладкой. Править — в репозитории, через dev и main.
- **Приёмник `bin/qodex-release`** менять только из репозитория (`deploy/server/qodex-release`) и после
  `bash deploy/server/test-qodex-release.sh`.
- **Строку ключа выкладки в `authorized_keys`:** не убирать `restrict,command="…"`.
- **Строки с пометкой `# managed by Certbot`** в `sites-enabled/qodex.tech`: по ним certbot продлевает
  сертификат. Certbot при продлении может переписать оформление этого файла — образец всегда
  в репозитории (`deploy/nginx/qodex.tech.conf`).
- **Отправщик писем** (`/opt/mail-sender`, служба `mail.service`): новый сайт отправляет заявки через него.
  Адрес `/api/request` и ответ `{"status": "Письмо успешно отправлено"}` не менять, не останавливать
  службу. Пароль от почты — только в unit-файле на сервере, не в репозитории.
- **nginx — только `reload`.** `restart` обрывает соединения всех сайтов сервера.
- **Прежний сайт `/opt/qodex-promo`** оставлен для возврата. Его выкладка из репозитория
  SIGNALL-D/qodex-promo-nuxt3 по-прежнему пишет туда; после переключения её лучше отключить
  (Actions → workflow → Disable workflow), чтобы правки туда не принимали за правки боевого сайта.
- **Закрытый ключ выкладки** — только в секрете GitHub и в `.secrets` у разработчика. Не в репозитории,
  не в чатах. Если он утёк — удалить его строку из `authorized_keys`, сделать новый (шаг 2) и заменить
  секрет `DEPLOY_SSH_KEY`.

## Файлы в репозитории

| Файл | Что делает |
|---|---|
| `.github/workflows/deploy-prod.yml` | сборка и проверки на dev и main, выкладка main, ручные rollback и status (только SIGNALL-D/qodex-site) |
| `.github/workflows/deploy.yml` | предварительная версия на GitHub Pages (только kavabangaga/qodex_new_promo), закрыта от поисковиков |
| `deploy/ci/check-dist.sh` | проверка сборки перед выкладкой |
| `deploy/ci/pack.sh` | MANIFEST.sha256 и архив |
| `deploy/ci/ssh-setup.sh`, `deploy/ci/remote.sh` | ключ и команды приёмнику по ssh (сервер проверяется по отпечатку) |
| `deploy/ci/deploy.sh` | выкладка архива и разбор ответа: «уже есть» — переключение на неё, ответ не дошёл — status |
| `deploy/ci/smoke.sh` | проверка qodex.tech снаружи после выкладки и отката |
| `deploy/server/qodex-release` | приёмник на сервере: deploy, rollback, status |
| `deploy/server/test-qodex-release.sh` | проверка приёмника и `deploy/ci/deploy.sh` без сервера (Linux или Git Bash) |
| `deploy/nginx/*.conf` | настройки nginx для qodex.tech |
| `deploy/nginx/REDIRECTS.md` | таблица переадресаций со старых адресов |
| `version4/src/config/build.ts` | номер версии в страницах, закрытие предварительной версии от поисковиков, canonical на qodex.tech |
| `version4/src/pages/robots.txt.ts`, `version4/integrations/sitemap.mjs` | robots.txt и карта сайта |
