#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QODEX weeek-bridge: каждая заявка с сайта qodex.tech — карточка в CRM Weeek.

Письмо о заявке по-прежнему отправляет старый отправщик (mail.service, POST /api/request). nginx копирует
тот же запрос сюда (директива mirror): POST /lead с тем же JSON {name, phone, email, company, comment}.
Ответ мосту nginx не нужен и посетителю не показывается, поэтому письмо уходит, даже если Weeek недоступен.

Что делает с заявкой:
  1. проверяет поля и отсеивает мусор (без имени, без телефона или почты, без отметки о согласии — не наша форма);
  2. кладёт заявку в очередь на диске (QUEUE_DIR) и сразу отвечает 202;
  3. фоновый поток ищет в CRM контакт с тем же телефоном (последние 10 цифр) или почтой — поиск Weeek нечёткий,
     поэтому совпадение перепроверяется здесь; не нашёл — создаёт контакт;
  4. заводит сделку в колонке WEEEK_STATUS_ID (воронка «Сайт qodex.tech», «Новая заявка») с привязанным контактом;
  5. если Weeek не ответил или ответил 429/5xx — повторяет с нарастающей паузой до GIVE_UP_HOURS, потом
     переносит заявку в QUEUE_DIR/failed; на прочие 4xx — сразу в failed (ошибка в данных, повтор не поможет).

Только стандартная библиотека Python 3.8+. Слушает 127.0.0.1:$LISTEN_PORT (по умолчанию 9031).
Настройки — из переменных окружения (weeek-bridge.env.example, README.md). Ключ Weeek — только там.
В журнал (stdout → journald) пишутся строки состояния без имён и телефонов.

    python3 weeek_bridge.py            # запустить мост
    python3 weeek_bridge.py --check    # проверить ключ и колонку (только чтение) и выйти
"""
from __future__ import annotations

import argparse
import html
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

LEAD_PATH = "/lead"
HEALTH_PATH = "/health"
MAX_BODY = 16 * 1024  # байт, как client_max_body_size у /api/request в nginx
LIMITS = {"name": 200, "phone": 60, "email": 200, "company": 255, "comment": 6000}
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
CONSENT_MARK = "Согласие на обработку персональных данных"
API_TIMEOUT = 15  # секунд на один запрос к Weeek
BACKOFF = [30, 60, 120, 300, 600, 1800]  # пауза перед повтором; дальше — каждые 30 минут


def env(name: str, default: Optional[str] = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        sys.exit(f"weeek-bridge: не задана переменная окружения {name}")
    return value


class Config:
    def __init__(self) -> None:
        self.token = env("WEEEK_TOKEN")
        self.status_id = env("WEEEK_STATUS_ID")
        self.base = env("WEEEK_BASE", "https://api.weeek.net/public/v1").rstrip("/")
        self.assignees = [a.strip() for a in os.environ.get("WEEEK_ASSIGNEES", "").split(",") if a.strip()]
        self.tags = [int(t) for t in os.environ.get("WEEEK_TAGS", "").split(",") if t.strip()]
        self.host = os.environ.get("LISTEN_HOST", "127.0.0.1")
        self.port = int(os.environ.get("LISTEN_PORT", "9031"))
        self.queue = Path(env("QUEUE_DIR", "/var/lib/qodex-weeek/queue"))
        self.give_up = float(os.environ.get("GIVE_UP_HOURS", "72")) * 3600
        self.require_consent = os.environ.get("REQUIRE_CONSENT", "1") != "0"
        self.title_prefix = os.environ.get("TITLE_PREFIX", "Заявка с сайта")


def log(msg: str) -> None:
    print(f"weeek-bridge: {msg}", flush=True)


# ── Проверка заявки ──────────────────────────────────────────────────────────────────────────────────────

def digits10(phone: str) -> str:
    """Последние 10 цифр телефона: «+7 (917) 000-00-00», «89170000000» и «9170000000» — один номер."""
    return re.sub(r"\D", "", phone or "")[-10:]


def clean_lead(raw: object, require_consent: bool = True) -> Tuple[Optional[Dict[str, str]], str]:
    """Нормализует заявку. Возвращает (заявка, "") или (None, причина отказа — без личных данных)."""
    if not isinstance(raw, dict):
        return None, "не объект JSON"
    lead: Dict[str, str] = {}
    for key, limit in LIMITS.items():
        value = raw.get(key)
        if value is None or value == "None":
            value = ""
        if not isinstance(value, str):
            return None, f"поле {key} не строка"
        value = value.replace("\r\n", "\n").strip()
        if len(value) > limit:
            return None, f"поле {key} длиннее {limit}"
        lead[key] = value
    if not lead["name"]:
        return None, "нет имени"
    if lead["email"] and not EMAIL_RE.match(lead["email"]):
        lead["email"] = ""  # кривую почту не кладём в контакт, она останется в описании сделки
    if len(digits10(lead["phone"])) < 10 and not lead["email"]:
        return None, "нет телефона и почты"
    if require_consent and CONSENT_MARK not in lead["comment"]:
        return None, "нет отметки о согласии (не форма сайта)"
    return lead, ""


# ── Weeek API ────────────────────────────────────────────────────────────────────────────────────────────

class WeeekError(Exception):
    def __init__(self, status: int, detail: str, retry: bool) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.retry = retry


class Weeek:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def call(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.cfg.base + path, data=data, method=method, headers={
            "Authorization": "Bearer " + self.cfg.token,
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "qodex-weeek-bridge/1",
        })
        try:
            with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
                payload = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            detail = e.read()[:200].decode("utf-8", "replace").replace("\n", " ")
            raise WeeekError(e.code, detail, retry=e.code == 429 or e.code >= 500) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            raise WeeekError(0, type(e).__name__, retry=True) from None
        if isinstance(payload, dict) and payload.get("success") is False:
            raise WeeekError(200, "success=false", retry=False)
        return payload

    def find_contact(self, phone: str, email: str) -> Optional[dict]:
        """Ищет контакт по телефону и почте. Поиск Weeek нечёткий — совпадение перепроверяем сами."""
        want_phone, want_email = digits10(phone), email.lower()
        queries = [q for q in (want_phone if len(want_phone) == 10 else "", want_email) if q]
        for q in queries:
            found = self.call("GET", "/crm/contacts?limit=50&search=" + urllib.parse.quote(q)).get("contacts") or []
            for contact in found:
                phones = {digits10(p.get("phone", "")) for p in contact.get("phones") or []}
                emails = {(e.get("email") or "").lower() for e in contact.get("emails") or []}
                if (want_phone and want_phone in phones) or (want_email and want_email in emails):
                    return contact
        return None

    def ensure_contact(self, lead: Dict[str, str]) -> str:
        contact = self.find_contact(lead["phone"], lead["email"])
        if contact:
            # у найденного контакта нет этой почты или телефона — дописываем, ошибку не считаем провалом
            have_phones = {digits10(p.get("phone", "")) for p in contact.get("phones") or []}
            have_emails = {(e.get("email") or "").lower() for e in contact.get("emails") or []}
            try:
                if len(digits10(lead["phone"])) == 10 and digits10(lead["phone"]) not in have_phones:
                    self.call("POST", f"/crm/contacts/{contact['id']}/phones", {"phone": lead["phone"]})
                if lead["email"] and lead["email"].lower() not in have_emails:
                    self.call("POST", f"/crm/contacts/{contact['id']}/emails", {"email": lead["email"]})
            except WeeekError as e:
                log(f"контакт найден, дописать телефон/почту не вышло: {e}")
            return contact["id"]
        body: dict = {"firstName": lead["name"]}
        if len(digits10(lead["phone"])) == 10:
            body["phones"] = [lead["phone"]]
        if lead["email"]:
            body["emails"] = [lead["email"]]
        created = self.call("POST", "/crm/contacts", body).get("contact") or {}
        if not created.get("id"):
            raise WeeekError(200, "контакт создан без id", retry=False)
        return created["id"]

    def create_deal(self, lead: Dict[str, str], contact_id: str, lead_id: str) -> str:
        body: dict = {
            "title": deal_title(lead, self.cfg.title_prefix),
            "description": deal_description(lead, lead_id),
            "contacts": [contact_id],
        }
        if self.cfg.assignees:
            body["assignees"] = self.cfg.assignees
        if self.cfg.tags:
            body["tags"] = self.cfg.tags
        deal = self.call("POST", f"/crm/statuses/{self.cfg.status_id}/deals", body).get("deal") or {}
        if not deal.get("id"):
            raise WeeekError(200, "сделка создана без id", retry=False)
        return str(deal["id"])


def deal_title(lead: Dict[str, str], prefix: str) -> str:
    who = " — ".join(x for x in (lead["company"], lead["name"]) if x)
    return f"{prefix}: {who}"[:255]


def deal_description(lead: Dict[str, str], lead_id: str) -> str:
    """Описание сделки: контакты и всё, что форма прислала в comment, — по абзацу на строку."""
    rows = [("Имя", lead["name"]), ("Телефон", lead["phone"]), ("Почта", lead["email"]), ("Компания", lead["company"])]
    parts = [f"<p><b>{k}:</b> {html.escape(v)}</p>" for k, v in rows if v]
    parts += [f"<p>{html.escape(line)}</p>" for line in lead["comment"].split("\n") if line.strip()]
    parts.append(f"<p>Заявка с сайта qodex.tech, № {html.escape(lead_id)}</p>")
    return "".join(parts)


# ── Очередь на диске ─────────────────────────────────────────────────────────────────────────────────────

class Queue:
    """Файл на заявку: {lead, received, attempts, next_try, contact_id}. Удаляется, когда сделка заведена."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.failed = root / "failed"
        self.failed.mkdir(parents=True, exist_ok=True)
        os.chmod(root, 0o700)
        os.chmod(self.failed, 0o700)

    def put(self, lead: Dict[str, str]) -> str:
        lead_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        self.write(lead_id, {"lead": lead, "received": time.time(), "attempts": 0, "next_try": 0, "contact_id": None})
        return lead_id

    def write(self, lead_id: str, item: dict) -> None:
        tmp = self.root / f".{lead_id}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(item, f, ensure_ascii=False)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.root / f"{lead_id}.json")

    def items(self) -> List[Tuple[str, dict]]:
        out = []
        for path in sorted(self.root.glob("*.json")):
            try:
                out.append((path.stem, json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError):
                log(f"не читается файл очереди {path.name}, перенесён в failed")
                os.replace(path, self.failed / path.name)
        return out

    def done(self, lead_id: str) -> None:
        (self.root / f"{lead_id}.json").unlink(missing_ok=True)

    def fail(self, lead_id: str) -> None:
        src = self.root / f"{lead_id}.json"
        if src.exists():
            os.replace(src, self.failed / src.name)

    def size(self) -> int:
        return len(list(self.root.glob("*.json")))


class Worker(threading.Thread):
    def __init__(self, cfg: Config, queue: Queue, api: Weeek) -> None:
        super().__init__(daemon=True)
        self.cfg, self.queue, self.api = cfg, queue, api
        self.wake = threading.Event()

    def run(self) -> None:
        while True:
            self.process_all()
            self.wake.wait(timeout=30)
            self.wake.clear()

    def process_all(self) -> None:
        now = time.time()
        for lead_id, item in self.queue.items():
            if item.get("next_try", 0) > now:
                continue
            self.process(lead_id, item)

    def process(self, lead_id: str, item: dict) -> None:
        try:
            if not item.get("contact_id"):
                item["contact_id"] = self.api.ensure_contact(item["lead"])
                self.queue.write(lead_id, item)  # при повторе контакт второй раз не создастся
            deal_id = self.api.create_deal(item["lead"], item["contact_id"], lead_id)
        except WeeekError as e:
            item["attempts"] = item.get("attempts", 0) + 1
            too_old = time.time() - item.get("received", 0) > self.cfg.give_up
            if e.retry and not too_old:
                item["next_try"] = time.time() + BACKOFF[min(item["attempts"] - 1, len(BACKOFF) - 1)]
                self.queue.write(lead_id, item)
                log(f"заявка {lead_id}: Weeek {e} — повтор №{item['attempts']}")
            else:
                self.queue.write(lead_id, item)
                self.queue.fail(lead_id)
                log(f"заявка {lead_id}: Weeek {e} — не заведена, перенесена в failed")
            return
        self.queue.done(lead_id)
        log(f"заявка {lead_id}: сделка {deal_id} заведена")


# ── HTTP ─────────────────────────────────────────────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "qodex-weeek-bridge"
    sys_version = ""
    cfg: Config
    queue: Queue
    worker: Worker

    def log_message(self, fmt: str, *args) -> None:  # без IP и тела запроса
        pass

    def reply(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == HEALTH_PATH:
            self.reply(200, {"ok": True, "queue": self.queue.size()})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != LEAD_PATH:
            self.reply(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length <= 0 or length > MAX_BODY:
            self.reply(413 if length > MAX_BODY else 400, {"error": "bad length"})
            return
        try:
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "bad json"})
            return
        lead, why = clean_lead(raw, self.cfg.require_consent)
        if lead is None:
            log(f"заявка отклонена: {why}")
            self.reply(422, {"error": why})
            return
        lead_id = self.queue.put(lead)
        log(f"заявка {lead_id} принята")
        self.worker.wake.set()
        self.reply(202, {"ok": True, "id": lead_id})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def check(cfg: Config) -> int:
    """Только чтение: ключ рабочий, колонка существует."""
    api = Weeek(cfg)
    try:
        me = api.call("GET", "/user/me").get("user") or {}
        status = api.call("GET", f"/crm/statuses/{cfg.status_id}").get("status") or {}
    except WeeekError as e:
        print(f"ошибка: {e}")
        return 1
    print(f"ключ рабочий (пользователь {me.get('id', '?')}), колонка «{status.get('name', '?')}» найдена")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Заявки с сайта → CRM Weeek")
    parser.add_argument("--check", action="store_true", help="проверить ключ и колонку и выйти")
    args = parser.parse_args(argv)
    cfg = Config()
    if args.check:
        return check(cfg)
    queue = Queue(cfg.queue)
    worker = Worker(cfg, queue, Weeek(cfg))
    worker.start()
    Handler.cfg, Handler.queue, Handler.worker = cfg, queue, worker
    server = Server((cfg.host, cfg.port), Handler)
    log(f"слушает {cfg.host}:{cfg.port}, в очереди {queue.size()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
