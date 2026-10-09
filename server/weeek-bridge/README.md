# Заявки с сайта → CRM Weeek

Каждая заявка с формы qodex.tech уходит двумя независимыми путями:

1. **Письмо на info@qodex.tech** — старый отправщик `mail.service` (`/opt/mail-sender`, POST `/api/request` → 127.0.0.1:9012).
2. **Карточка в CRM Weeek** — этот мост `qodex-weeek-bridge` (127.0.0.1:9031). nginx копирует тот же запрос
   сюда директивой `mirror` (vhost qodex.tech, `location = /api/request` → `location = /_qodex_weeek`).
   Ответ моста никому не нужен: если Weeek или мост лежат, письмо всё равно уходит, а посетитель видит «отправлено».

Что делает мост с заявкой:

- отсеивает мусор: без имени, без телефона (или почты), без строки о согласии — значит, прислала не форма сайта;
- кладёт заявку в очередь на диске `/var/lib/qodex-weeek/queue` и сразу отвечает;
- ищет в CRM контакт с тем же телефоном (сравниваются последние 10 цифр) или почтой; нет — создаёт контакт;
- заводит сделку в воронке **«Сайт qodex.tech»**, колонка **«Новая заявка»**, с привязанным контактом.
  Название — «Заявка с сайта: Компания — Имя», в описании всё, что прислала форма (продукты, откуда, страница,
  согласие, время), и номер заявки;
- Weeek не ответил или ответил 429/5xx — повторяет с паузой (30 с … 30 мин) до 72 часов, потом переносит
  заявку в `queue/failed`. Другие ошибки (4xx) — сразу в `failed`.

В журнал (`journalctl -u qodex-weeek-bridge`) пишутся только номера заявок и сделок, без имён и телефонов.

## Установка (один раз, администратор сервера)

```bash
D=$(mktemp -d)                                  # сюда скопировать weeek_bridge.py и qodex-weeek-bridge.service
sudo install -d -m 755 /opt/qodex-weeek
sudo install -m 644 "$D/weeek_bridge.py" /opt/qodex-weeek/weeek_bridge.py
sudo install -d -o qodex -g qodex -m 700 /var/lib/qodex-weeek /var/lib/qodex-weeek/queue
sudo install -d -m 755 /etc/qodex
sudo install -o root -g qodex -m 640 /dev/null /etc/qodex/weeek-bridge.env
sudoedit /etc/qodex/weeek-bridge.env            # по образцу weeek-bridge.env.example, ключ вписать сюда
sudo install -m 644 "$D/qodex-weeek-bridge.service" /etc/systemd/system/qodex-weeek-bridge.service
sudo systemctl daemon-reload
sudo -u qodex env $(sudo cat /etc/qodex/weeek-bridge.env | grep -v '^#' | xargs) \
  python3 /opt/qodex-weeek/weeek_bridge.py --check   # только чтение: ключ рабочий, колонка найдена
sudo systemctl enable --now qodex-weeek-bridge
curl -s http://127.0.0.1:9031/health             # {"ok": true, "queue": 0}
```

## Обслуживание

- **Что в очереди:** `curl -s http://127.0.0.1:9031/health`, файлы — `sudo ls /var/lib/qodex-weeek/queue{,/failed}`.
- **Повторить заявку из failed:** `sudo mv /var/lib/qodex-weeek/queue/failed/<файл> /var/lib/qodex-weeek/queue/`
  — мост подхватит её в течение 30 секунд.
- **Сменить колонку, ответственного или ключ:** `sudoedit /etc/qodex/weeek-bridge.env`, затем
  `sudo systemctl restart qodex-weeek-bridge`.
- **Обновить код:** скопировать новый `weeek_bridge.py` в `/opt/qodex-weeek/` и перезапустить службу.
- **Тесты (без сети, на поддельном Weeek):** `python3 test_weeek_bridge.py`.

## API Weeek, которым пользуется мост

База `https://api.weeek.net/public/v1`, заголовок `Authorization: Bearer <ключ>` (документация —
https://developers.weeek.net/api):

- `GET /crm/contacts?search=…` — поиск контакта (нечёткий: мост сам сверяет телефон и почту);
- `POST /crm/contacts` `{firstName, phones, emails}` — новый контакт;
- `POST /crm/contacts/{id}/phones` / `/emails` — дописать найденному контакту новый телефон или почту;
- `POST /crm/statuses/{statusId}/deals` `{title, description, contacts, assignees, tags}` — сделка в колонке;
- `GET /user/me`, `GET /crm/statuses/{id}` — проверка `--check`.
