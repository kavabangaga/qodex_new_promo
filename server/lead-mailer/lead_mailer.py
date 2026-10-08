#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QODEX lead mailer: приёмник заявок с формы сайта qodex.tech.

Принимает POST /api/lead (JSON от формы сайта), проверяет поля и отправляет каждую заявку одним письмом
на почту компании через SMTP (почта домена qodex.tech — Mail.ru / VK WorkSpace). После того как почтовый
сервер принял письмо, дописывает запись о согласии на обработку персональных данных в CONSENT_LOG
(доказательство согласия, хранится три года — п. 6.5 текста согласия на сайте).

Только стандартная библиотека Python 3.8+. Слушает 127.0.0.1:$PORT (по умолчанию 8787) за nginx.
Настройки берутся только из переменных окружения (см. lead-mailer.env.example и README.md).

    python3 lead_mailer.py                                # запустить приёмник
    python3 lead_mailer.py --purge-older-than-days 1095   # удалить записи о согласии старше N дней и выйти

В журнал (stderr → journald) пишутся только строки состояния: без имён, телефонов и IP-адресов.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import email.headerregistry
import email.message
import email.utils
import errno
import http.server
import ipaddress
import json
import math
import os
import re
import signal
import smtplib
import socketserver
import ssl
import sys
import tempfile
import threading
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

try:  # POSIX: блокировка файла записей о согласии между приёмником и очисткой по cron
    import fcntl
except ImportError:  # Windows — только для локальных тестов
    fcntl = None  # type: ignore[assignment]

API_PATH = "/api/lead"
MAX_BODY = 16 * 1024  # байт; nginx режет раньше (client_max_body_size 16k)
BODY_DEADLINE = 30  # секунд на всё тело запроса, как бы медленно его ни присылали (дальше — 408)
DRAIN_LIMIT = 256 * 1024  # слишком большое тело дочитываем до этого предела, чтобы ответ 413 дошёл до клиента…
DRAIN_DEADLINE = 5  # …но не дольше этого (секунд)
RATE_LIMIT = 5  # принятых заявок с одного адреса (IPv4 или сети IPv6 /64)…
RATE_WINDOW = 10 * 60  # …за 10 минут
DEFAULT_MAX_PER_HOUR = 30  # общий потолок: принятых заявок со всех адресов за час (MAX_LEADS_PER_HOUR)
TOTAL_WINDOW = 60 * 60
SMTP_TIMEOUT = 10  # секунд на каждое действие с почтовым сервером (соединение, ответ на команду)
# Худший случай одной отправки: соединение с каждым из 3 адресов smtp.mail.ru (AAAA и две A) + TLS (2)
# + 8 ответов сервера (приветствие, EHLO, AUTH, MAIL, RCPT, DATA, конец письма, QUIT), по SMTP_TIMEOUT на каждое.
# proxy_read_timeout в nginx-api-lead.conf должен быть больше: иначе nginx ответит посетителю 504, письмо всё равно
# уйдёт, а посетитель отправит заявку ещё раз (второе письмо). Каждый лишний адрес в MAIL_TO — ещё один RCPT.
SMTP_WORST_CASE = SMTP_TIMEOUT * (3 + 2 + 8)  # 130 с; в nginx — 150 с
HANDLER_TIMEOUT = 20  # секунд на каждое чтение строки запроса и заголовков
MIN_FREE_BYTES = 1024 * 1024  # меньше свободного места у файла записей о согласии — заявки не принимаем (503)
DEFAULT_CONSENT_LOG = "/var/lib/qodex-lead/consent.jsonl"
SITE_NAME = "qodex.tech"

UTC = dt.timezone.utc
MSK = dt.timezone(dt.timedelta(hours=3))  # Москва: UTC+3 круглый год

# id продуктов — как в форме сайта (version4/src/config/site.ts, PRODUCT_ORDER); порядок — тот же
PRODUCTS: Tuple[Tuple[str, str], ...] = (
    ("robot", "РО-БОТ"),
    ("tracker", "QODEX Tracker"),
    ("tonn", "QODEX TONN"),
    ("kodeks", "Кодекс ТКО"),
)
PRODUCT_NAMES: Dict[str, str] = dict(PRODUCTS)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
# Телефон. Форма сайта пропускает любую строку, где не меньше 10 цифр, поэтому правило здесь мягкое (то же правило
# нужно повторить в проверке формы, version4/src/components/LeadForm.astro):
#   1) любое тире (‐ ‑ ‒ – — ― −) считается дефисом;
#   2) добавочный номер в конце («доб. 5», «доп 12», «вн. 123», «ext 5», «x5», «#12») отделяется;
#   3) основной номер — первый фрагмент из цифр, пробелов и знаков + ( ) - . /, в котором от 10 до 15 цифр.
# Остальное, что человек ввёл (например, «, Иван»), не мешает: в письме оно видно в скобках «введено: …».
PHONE_DASHES = str.maketrans({ch: "-" for ch in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"})
PHONE_EXT_RE = re.compile(
    r"[\s,;]*(?:доб(?:авочный)?|доп|вн(?:утр(?:енний)?)?|ext(?:ension)?|x|#)\.?\s*:?\s*([0-9]{1,6})$",
    re.IGNORECASE,
)
PHONE_RUN_RE = re.compile(r"[+(]*[0-9][0-9()\-./ ]*[0-9]")
UTM_KEY_RE = re.compile(r"utm_[A-Za-z0-9_]{1,40}")
URL_RE = re.compile(r"https?://", re.IGNORECASE)
WS_RE = re.compile(r"\s+")

O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
O_BINARY = getattr(os, "O_BINARY", 0)  # Windows: без перевода \n в \r\n


# ---------------------------------------------------------------------------------------------------------------
# Общие помощники


def log(message: str) -> None:
    """Строка состояния в stderr (под systemd — в journald). Имён, телефонов и IP-адресов здесь не бывает."""
    try:
        sys.stderr.write("lead-mailer: " + message + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def clean(value: object, limit: Optional[int] = None) -> str:
    """Одна строка без управляющих символов.

    Любые пробельные символы (в том числе CR, LF, TAB, перевод строки Юникода) становятся одним пробелом,
    остальные непечатаемые (управляющие, невидимые, переключатели направления текста) удаляются.
    Так ни одно значение из заявки не может добавить строку ни в заголовки письма, ни в его текст.
    """
    if not isinstance(value, str):
        return ""
    text = WS_RE.sub(" ", value)
    text = "".join(ch for ch in text if ch.isprintable())
    text = text.strip()
    return text[:limit] if limit is not None else text


def parse_utc(value: str) -> dt.datetime:
    """ISO 8601 → время в UTC. Понимает и «Z» на конце (так пишет браузер), в том числе в Python 3.8–3.10."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    moment = dt.datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def fmt(moment: dt.datetime) -> str:
    return moment.strftime("%d.%m.%Y %H:%M:%S")


# ---------------------------------------------------------------------------------------------------------------
# Настройки


class ConfigError(Exception):
    pass


class Config:
    def __init__(self, env: Dict[str, str]) -> None:
        def get(name: str, default: str = "") -> str:
            return (env.get(name) or default).strip()

        self.smtp_host = get("SMTP_HOST", "smtp.mail.ru")
        self.smtp_ssl = get("SMTP_SSL", "1").lower() not in ("0", "no", "false", "off")
        self.smtp_user = get("SMTP_USER")
        self.smtp_password = env.get("SMTP_PASSWORD") or ""  # пароль не обрезаем: берём ровно как записан
        self.mail_to = [a.strip() for a in get("MAIL_TO", "info@qodex.tech").split(",") if a.strip()]
        self.consent_log = get("CONSENT_LOG", DEFAULT_CONSENT_LOG)

        missing = [n for n, v in (("SMTP_USER", self.smtp_user), ("SMTP_PASSWORD", self.smtp_password)) if not v]
        if missing:
            raise ConfigError("не заданы " + ", ".join(missing) + " (файл окружения службы, см. README.md)")
        if any(ch in self.smtp_password for ch in "\r\n"):
            raise ConfigError("SMTP_PASSWORD содержит перевод строки")
        for name, addr in [("SMTP_USER", self.smtp_user)] + [("MAIL_TO", a) for a in self.mail_to]:
            if not EMAIL_RE.fullmatch(addr):
                raise ConfigError(name + " — не похоже на адрес почты: " + clean(addr, 80))
        if not self.mail_to:
            raise ConfigError("MAIL_TO пуст")
        try:
            self.smtp_port = int(get("SMTP_PORT", "465"))
            self.port = int(get("PORT", "8787"))
        except ValueError:
            raise ConfigError("SMTP_PORT и PORT должны быть числами") from None
        if not (0 < self.smtp_port < 65536 and 0 < self.port < 65536):
            raise ConfigError("SMTP_PORT и PORT — от 1 до 65535")
        if not self.smtp_ssl and self.smtp_host not in ("127.0.0.1", "::1", "localhost"):
            # без шифрования пароль ушёл бы по сети открытым текстом
            raise ConfigError("SMTP_SSL=0 разрешён только для локального теста (SMTP_HOST=127.0.0.1)")
        if not self.consent_log:
            raise ConfigError("CONSENT_LOG пуст")
        try:
            self.max_per_hour = int(get("MAX_LEADS_PER_HOUR", str(DEFAULT_MAX_PER_HOUR)))
        except ValueError:
            raise ConfigError("MAX_LEADS_PER_HOUR должно быть числом") from None
        if not 1 <= self.max_per_hour <= 100000:
            raise ConfigError("MAX_LEADS_PER_HOUR — от 1 до 100000")
        # имя для приветствия EHLO: домен ящика (иначе smtplib спрашивает имя машины у DNS)
        self.ehlo_name = self.smtp_user.rsplit("@", 1)[1]


# ---------------------------------------------------------------------------------------------------------------
# Проверка заявки


class Invalid(Exception):
    """Поле заявки не прошло проверку; в ответ уходит 400 с названием поля."""

    def __init__(self, field: str) -> None:
        super().__init__(field)
        self.field = field


class Lead:
    __slots__ = ("name", "phone", "phone_ext", "phone_typed", "products", "tracker_demo", "utm", "page", "sent_at",
                 "consent_edition", "consent_text")

    def __init__(self, **fields: object) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


def normalize_phone(plus: bool, digits: str) -> str:
    """Номер в виде +7XXXXXXXXXX, когда это однозначно; иначе — только цифры (с «+», если его ввели)."""
    if plus:
        return "+" + digits
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return "+7" + digits
    return digits


def parse_phone(raw: object) -> Tuple[str, str, str]:
    """(основной номер, добавочный или «», как ввели). Правило — у PHONE_RUN_RE выше."""
    if not isinstance(raw, str):
        raise Invalid("phone")
    typed = clean(raw, 60)
    text = typed.translate(PHONE_DASHES).rstrip(" ,;.")
    ext = ""
    match = PHONE_EXT_RE.search(text)
    if match:
        ext = match.group(1)
        text = text[:match.start()]
    for run in PHONE_RUN_RE.finditer(text):
        number = run.group()
        digits = re.sub(r"[^0-9]", "", number)
        if 10 <= len(digits) <= 15:
            prefix = number[:len(number) - len(number.lstrip("+("))]
            return normalize_phone("+" in prefix, digits), ext, typed
    raise Invalid("phone")


def parse_lead(data: object) -> Lead:
    if not isinstance(data, dict):
        raise Invalid("body")

    raw_name = data.get("name")
    name = clean(raw_name)
    if not isinstance(raw_name, str) or not 1 <= len(name) <= 100:
        raise Invalid("name")

    phone, phone_ext, phone_typed = parse_phone(data.get("phone"))

    interest = data.get("interest")
    if interest is None:
        interest = []
    if (not isinstance(interest, list) or len(interest) > 10
            or not all(isinstance(pid, str) and pid in PRODUCT_NAMES for pid in interest)):
        raise Invalid("interest")
    products = [pid for pid, _ in PRODUCTS if pid in interest]

    utm: Dict[str, str] = {}
    raw_utm = data.get("utm")
    if isinstance(raw_utm, dict):
        for key, value in list(raw_utm.items())[:20]:
            if isinstance(key, str) and UTM_KEY_RE.fullmatch(key) and isinstance(value, str):
                value = clean(value, 200)
                if value:
                    utm[key.lower()] = value
            if len(utm) >= 10:
                break

    page = clean(data.get("page"), 500)
    if not URL_RE.match(page):
        page = ""

    consent = data.get("consent")
    if not isinstance(consent, dict) or consent.get("given") is not True:
        raise Invalid("consent")
    edition = clean(consent.get("edition"))
    if not 1 <= len(edition) <= 20:
        raise Invalid("consent")
    consent_text = clean(consent.get("text"))
    if not 1 <= len(consent_text) <= 300 or not URL_RE.match(consent_text):
        raise Invalid("consent")

    return Lead(
        name=name,
        phone=phone,
        phone_ext=phone_ext,
        phone_typed=phone_typed,
        products=products,
        tracker_demo=data.get("trackerDemo") is True,
        utm=utm,
        page=page,
        sent_at=clean(data.get("sentAt"), 40),
        consent_edition=edition,
        consent_text=consent_text,
    )


# ---------------------------------------------------------------------------------------------------------------
# Письмо


def subject_for(lead: Lead) -> str:
    names = ", ".join(PRODUCT_NAMES[pid] for pid in lead.products) or "продукт не выбран"
    return "Заявка с сайта " + SITE_NAME + ": " + names


def body_for(lead: Lead, received: dt.datetime) -> str:
    phone = lead.phone + (" доб. " + lead.phone_ext if lead.phone_ext else "")
    phone += " (введено: " + lead.phone_typed + ")" if lead.phone_typed != phone else ""
    products = ", ".join(PRODUCT_NAMES[pid] for pid in lead.products) or "продукт не выбран"
    utm = "; ".join(key + "=" + value for key, value in lead.utm.items()) or "нет"

    if lead.sent_at:
        try:
            sent = fmt(parse_utc(lead.sent_at).astimezone(MSK)) + " МСК"
        except (ValueError, OverflowError):  # не ISO 8601 или год 1 / 9999 со сдвигом пояса
            sent = lead.sent_at
    else:
        sent = "не указано"

    lines = [
        "Новая заявка с сайта " + SITE_NAME,
        "",
        "Имя: " + lead.name,
        "Телефон: " + phone,
        "Интересует: " + products,
    ]
    if lead.tracker_demo:
        lines.append("Tracker: запрос демо (пилот не обещаем)")
    lines += [
        "Страница: " + (lead.page or "не указана"),
        "UTM: " + utm,
        "Отправлено: " + sent + " (время браузера)",
        "Получено: " + fmt(received.astimezone(MSK)) + " МСК / " + fmt(received) + " UTC (время сервера)",
        "Согласие на обработку персональных данных: дано, редакция от " + lead.consent_edition
        + ", текст: " + lead.consent_text,
        "",
        "-- ",
        "Письмо отправил приёмник заявок сайта " + SITE_NAME + ". В нём персональные данные: не пересылайте его",
        "на зарубежную почту и в зарубежные сервисы (согласие, раздел 4).",
    ]
    return "\n".join(lines) + "\n"


def build_message(cfg: Config, lead: Lead, received: dt.datetime) -> email.message.EmailMessage:
    msg = email.message.EmailMessage()
    # в заголовки попадают только постоянные строки, названия продуктов из списка выше и адреса из настроек
    msg["Subject"] = subject_for(lead)
    msg["From"] = email.headerregistry.Address(display_name="Сайт " + SITE_NAME, addr_spec=cfg.smtp_user)
    msg["To"] = ", ".join(cfg.mail_to)
    msg["Date"] = email.utils.format_datetime(received)
    msg["Message-ID"] = email.utils.make_msgid(domain=cfg.ehlo_name)
    msg["Auto-Submitted"] = "auto-generated"  # автоответчики на такие письма не отвечают
    msg.set_content(body_for(lead, received), charset="utf-8", cte="base64")
    return msg


def deliver(cfg: Config, msg: email.message.EmailMessage) -> Dict[str, Tuple[int, bytes]]:
    """Отправляет письмо. Возвращается только после того, как сервер принял его (иначе — исключение)."""
    if cfg.smtp_ssl:
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            cfg.smtp_host, cfg.smtp_port, local_hostname=cfg.ehlo_name, timeout=SMTP_TIMEOUT,
            context=ssl.create_default_context(),
        )
    else:  # только локальный тест (см. Config)
        client = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, local_hostname=cfg.ehlo_name, timeout=SMTP_TIMEOUT)
    try:
        client.login(cfg.smtp_user, cfg.smtp_password)
        return client.send_message(msg, from_addr=cfg.smtp_user, to_addrs=cfg.mail_to)
    finally:
        # письмо уже принято — сбой на прощании (QUIT) не должен превращаться в ошибку и повторную заявку
        try:
            client.quit()
        except Exception:
            client.close()


def smtp_error_label(exc: BaseException) -> str:
    """Описание ошибки для журнала: тип и код ответа сервера, без содержимого письма."""
    label = type(exc).__name__
    code = getattr(exc, "smtp_code", None)
    if code:
        label += " " + str(code)
    elif isinstance(exc, OSError) and exc.strerror:
        label += " (" + clean(exc.strerror, 80) + ")"
    return label


# ---------------------------------------------------------------------------------------------------------------
# Записи о согласии


@contextlib.contextmanager
def file_lock(path: str):
    """Исключительная блокировка рядом лежащего файла <path>.lock (POSIX). Её берут и приёмник при каждой записи,
    и очистка по cron, поэтому очистка не теряет запись, сделанную в ту же секунду."""
    if fcntl is None:
        yield
        return
    fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT | O_CLOEXEC, 0o600)
    try:
        if os.geteuid() == 0:  # очистку запустили от root: файл блокировки должен остаться у службы
            owner = os.stat(os.path.dirname(os.path.abspath(path)))
            if os.fstat(fd).st_uid != owner.st_uid:
                os.fchown(fd, owner.st_uid, owner.st_gid)
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)  # закрытие снимает блокировку


class ConsentLog:
    """JSON Lines: одна строка — одна запись о согласии. Файл создаётся с правами 0600."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()

    def check(self) -> None:
        """При запуске: файл можно создать и дописывать, права — только владельцу."""
        directory = os.path.dirname(os.path.abspath(self.path))
        if not os.path.isdir(directory):
            raise OSError(2, "нет папки " + directory)
        for path in (self.path, self.path + ".lock") if fcntl is not None else (self.path,):
            fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | O_CLOEXEC | O_BINARY, 0o600)
            try:
                if hasattr(os, "fchmod") and os.fstat(fd).st_mode & 0o077:
                    os.fchmod(fd, 0o600)
            finally:
                os.close(fd)

    def probe(self) -> None:
        """Перед отправкой письма: запись о согласии получится сохранить. Иначе письмо не отправляем (ответ 503):
        письмо — не доказательство на три года, его удаляют не позже чем через 30 дней (п. 6.3 согласия)."""
        with self._lock, file_lock(self.path):
            os.close(os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | O_CLOEXEC | O_BINARY, 0o600))
        if hasattr(os, "statvfs"):
            st = os.statvfs(os.path.dirname(os.path.abspath(self.path)))
            if st.f_bavail * st.f_frsize < MIN_FREE_BYTES:
                raise OSError(errno.ENOSPC, "мало места на диске")

    def append(self, record: Dict[str, object]) -> None:
        data = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock, file_lock(self.path):
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | O_CLOEXEC | O_BINARY, 0o600)
            try:
                view = memoryview(data)
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
            finally:
                os.close(fd)


def purge(path: str, days: int) -> int:
    """Удаляет записи, полученные больше `days` дней назад. Строки, которые не удалось разобрать, оставляет."""
    cutoff = dt.datetime.now(UTC) - dt.timedelta(days=days)
    if not os.path.exists(path):
        log("очистка: файла записей о согласии нет (" + path + ") — удалять нечего")
        return 0
    with file_lock(path):
        with open(path, "rb") as f:
            lines = f.read().splitlines()
        kept: List[bytes] = []
        removed = unparsed = 0
        for raw in lines:
            if not raw.strip():
                continue
            try:
                received = parse_utc(json.loads(raw.decode("utf-8"))["received_at"])
            except Exception:
                unparsed += 1
                kept.append(raw + b"\n")
                continue
            if received < cutoff:
                removed += 1
            else:
                kept.append(raw + b"\n")
        if removed:
            directory = os.path.dirname(os.path.abspath(path))
            st = os.stat(path)
            fd, tmp = tempfile.mkstemp(prefix=".consent-", suffix=".tmp", dir=directory)  # права 0600
            try:
                with os.fdopen(fd, "wb") as f:
                    f.writelines(kept)
                    f.flush()
                    os.fsync(f.fileno())
                if getattr(os, "geteuid", lambda: -1)() == 0:
                    os.chown(tmp, st.st_uid, st.st_gid)  # запущено от root — файл остаётся у службы
                os.replace(tmp, path)
            except BaseException:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
                raise
            if hasattr(os, "O_DIRECTORY"):
                dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
    log("очистка записей о согласии старше %d дн.: удалено %d, осталось %d%s"
        % (days, removed, len(kept), ", не разобрано (оставлены) %d" % unparsed if unparsed else ""))
    return removed


# ---------------------------------------------------------------------------------------------------------------
# Ограничение частоты


class RateLimiter:
    """Не больше `limit` принятых заявок с одного адреса за `window` секунд. Место занимается до отправки письма
    и освобождается, если отправить не удалось (ошибка почты не отнимает у человека попытку)."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self._hits: Dict[str, deque] = {}
        self._lock = threading.Lock()
        self._swept = time.monotonic()

    def reserve(self, key: str) -> Tuple[Optional[float], int]:
        """(метка, 0) — место занято; (None, через сколько секунд повторить) — лимит исчерпан."""
        now = time.monotonic()
        with self._lock:
            if now - self._swept > self.window:
                for k in [k for k, q in self._hits.items() if not q or q[-1] <= now - self.window]:
                    del self._hits[k]
                self._swept = now
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return None, max(1, math.ceil(hits[0] + self.window - now))
            hits.append(now)
            return now, 0

    def release(self, key: str, stamp: float) -> None:
        with self._lock:
            hits = self._hits.get(key)
            if hits is not None:
                with contextlib.suppress(ValueError):
                    hits.remove(stamp)


def rate_key(ip: str) -> str:
    """Чей это лимит. IPv4 — сам адрес. IPv6 — сеть /64: обычному хосту выдают её целиком, и иначе один человек
    менял бы адрес на каждую заявку. IPv4, записанный как IPv6 (::ffff:a.b.c.d), — снова сам IPv4."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip
    if isinstance(addr, ipaddress.IPv6Address):
        if addr.ipv4_mapped is not None:
            return str(addr.ipv4_mapped)
        return str(ipaddress.IPv6Network(((int(addr) >> 64) << 64, 64)))
    return str(addr)


# ---------------------------------------------------------------------------------------------------------------
# HTTP


class LeadServer(http.server.ThreadingHTTPServer):
    # Каждый запрос — в своём потоке. Потоки не фоновые, но сервер их не запоминает (block_on_close = False):
    # при остановке main() дожидается тех, что ещё отправляют письмо, а память не растёт с каждым соединением
    # (в Python 3.8 — 3.9.10 при block_on_close = True сервер копил все потоки в списке навсегда, bpo-37193).
    daemon_threads = False
    block_on_close = False
    request_queue_size = 128  # очередь входящих соединений: всплеск заявок не получает отказ в соединении

    def __init__(self, address: Tuple[str, int], cfg: Config, store: ConsentLog) -> None:
        self.cfg = cfg
        self.store = store
        self.limiter = RateLimiter(RATE_LIMIT, RATE_WINDOW)  # с одного адреса
        self.total_limiter = RateLimiter(cfg.max_per_hour, TOTAL_WINDOW)  # со всех адресов вместе, ключ «*»
        super().__init__(address, LeadHandler)

    def server_bind(self) -> None:
        # как у HTTPServer, но без обращения к DNS за именем машины
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name, self.server_port = str(host), int(port)


class LeadHandler(http.server.BaseHTTPRequestHandler):
    server: LeadServer
    server_version = "qodex-lead-mailer"
    sys_version = ""
    timeout = HANDLER_TIMEOUT

    # --- журнал: свои строки состояния вместо стандартных (там адрес клиента)

    def log_request(self, code: object = "-", size: object = "-") -> None:
        pass

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — сигнатура http.server
        log(clean(format % args, 200))

    # --- ответы

    def _path(self) -> str:
        return self.path.split("?", 1)[0]

    def _reply(self, code: int, payload: Dict[str, object], note: str = "",
               headers: Optional[Dict[str, str]] = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        lost = ""
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except OSError:  # посетитель или nginx закрыл соединение, не дождавшись ответа; заявка уже обработана
            self.close_connection = True
            lost = " (ответ не доставлен: соединение закрыто)"
        log("%s %s %d%s%s" % (self.command, clean(self._path(), 100), code, " " + note if note else "", lost))

    def _fail(self, code: int, error: str, note: str = "", headers: Optional[Dict[str, str]] = None) -> None:
        self._reply(code, {"ok": False, "error": error}, note or error, headers)

    def _not_post(self) -> None:
        if self._path() == API_PATH:
            self._fail(405, "method_not_allowed", headers={"Allow": "POST"})
        else:
            self._fail(404, "not_found")

    do_GET = do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _not_post

    # --- приём заявки

    def _client_ip(self) -> str:
        peer = self.client_address[0]
        try:
            from_proxy = ipaddress.ip_address(peer).is_loopback
        except ValueError:
            from_proxy = False
        if from_proxy:  # заголовок X-Real-IP ставит nginx; доверяем ему, только если запрос пришёл с этой машины
            try:
                return str(ipaddress.ip_address((self.headers.get("X-Real-IP") or "").strip()))
            except ValueError:
                pass
        return peer

    def _read_until(self, length: int, seconds: float, keep: bool) -> bytes:
        """Читает до `length` байт тела, но не дольше `seconds` в сумме (медленная присылка по байту не держит
        поток). По истечении срока — TimeoutError; конец соединения — меньше байт, чем просили."""
        deadline = time.monotonic() + seconds
        chunks: List[bytes] = []
        left = length
        try:
            while left > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("тело запроса не пришло вовремя")
                self.connection.settimeout(max(0.1, remaining))
                chunk = self.rfile.read1(min(left, 65536))
                if not chunk:
                    break
                left -= len(chunk)
                if keep:
                    chunks.append(chunk)
        finally:
            with contextlib.suppress(OSError):
                self.connection.settimeout(self.timeout)
        return b"".join(chunks)

    def _drain(self, length: int) -> None:
        """Дочитать лишнее тело (иначе ответ 413 может не дойти до клиента). Ошибки и срок — не важны: всё равно 413."""
        with contextlib.suppress(OSError):
            self._read_until(min(length, DRAIN_LIMIT), DRAIN_DEADLINE, keep=False)

    def do_POST(self) -> None:
        try:
            self._handle_post()
        except Exception as exc:  # непредвиденная ошибка: ответить, но без подробностей
            log("внутренняя ошибка: " + type(exc).__name__)
            self.close_connection = True
            with contextlib.suppress(Exception):
                self._fail(500, "internal")

    def _handle_post(self) -> None:
        if self._path() != API_PATH:
            self._fail(404, "not_found")
            return
        self.close_connection = True

        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            self._fail(415, "content_type")
            return
        if self.headers.get("Transfer-Encoding"):
            self._fail(411, "length_required")
            return
        try:
            length = int(self.headers.get("Content-Length") or "")
        except ValueError:
            self._fail(411, "length_required")
            return
        if length < 0:
            self._fail(400, "body")
            return
        if length > MAX_BODY:
            self._drain(length)
            self._fail(413, "too_large")
            return
        try:
            raw = self._read_until(length, BODY_DEADLINE, keep=True)
        except OSError:  # в том числе TimeoutError
            self._fail(408, "timeout")
            return
        if len(raw) != length:
            self._fail(400, "body")
            return
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:  # не UTF-8, не JSON, слишком глубокая вложенность
            self._fail(400, "json")
            return
        try:
            lead = parse_lead(data)
        except Invalid as exc:
            self._fail(400, exc.field, "invalid " + exc.field)
            return

        server = self.server
        cfg = server.cfg
        key = rate_key(self._client_ip())
        stamp, retry_after = server.limiter.reserve(key)
        if stamp is None:
            self._fail(429, "rate_limited", headers={"Retry-After": str(retry_after)})
            return
        total_stamp, retry_after = server.total_limiter.reserve("*")
        if total_stamp is None:
            server.limiter.release(key, stamp)
            self._fail(429, "rate_limited", "общий лимит: больше %d заявок за час со всех адресов" % cfg.max_per_hour,
                       headers={"Retry-After": str(retry_after)})
            return

        def release() -> None:  # заявка не принята не по вине посетителя: места в лимитах возвращаются
            server.limiter.release(key, stamp)
            server.total_limiter.release("*", total_stamp)

        try:
            server.store.probe()
        except Exception as exc:
            release()
            log("ОШИБКА: CONSENT_LOG недоступен (%s) — заявки не принимаются, проверьте права и место на диске"
                % (type(exc).__name__ + (" " + clean(exc.strerror, 80) if getattr(exc, "strerror", None) else "")))
            self._fail(503, "storage", "запись о согласии сохранить нельзя, письмо не отправлено")
            return

        received = dt.datetime.now(UTC).replace(microsecond=0)
        try:
            refused = deliver(cfg, build_message(cfg, lead, received))
        except Exception as exc:
            release()
            self._fail(502, "mail", "почтовый сервер не принял письмо: " + smtp_error_label(exc))
            return
        if refused:
            log("часть получателей отклонена почтовым сервером: %d из %d" % (len(refused), len(cfg.mail_to)))

        # доказательство согласия (п. 5.2 и 6.5 текста согласия) — только после того, как письмо принято.
        # Страница — без строки запроса и якоря: метки рекламы (utm, yclid, gclid) рядом с телефоном три года
        # не храним, они есть только в письме.
        record = {
            "received_at": received.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phone": lead.phone,
            "consent_given": True,
            "consent_edition": lead.consent_edition,
            "consent_text": lead.consent_text,
            "page": lead.page.split("#", 1)[0].split("?", 1)[0],
        }
        try:
            server.store.append(record)
        except Exception as exc:
            # Проверка выше прошла, но запись всё же не удалась (например, диск заполнился за эти секунды).
            # Письмо уже ушло (в нём те же сведения о согласии и время получения), поэтому заявку не отклоняем:
            # повтор дал бы второе письмо. Ошибку видно в журнале — администратору нужно её устранить.
            log("ОШИБКА: запись о согласии не сохранена (" + type(exc).__name__ + ") — проверьте CONSENT_LOG")
        self._reply(200, {"ok": True}, "заявка отправлена")


# ---------------------------------------------------------------------------------------------------------------
# Запуск


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="QODEX: приёмник заявок с сайта qodex.tech → почта.")
    parser.add_argument("--purge-older-than-days", type=int, metavar="N",
                        help="удалить из CONSENT_LOG записи старше N дней и выйти (cron: N=1095)")
    args = parser.parse_args(argv)

    if args.purge_older_than_days is not None:
        if args.purge_older_than_days < 1:
            parser.error("N должно быть больше нуля")
        try:
            purge((os.environ.get("CONSENT_LOG") or DEFAULT_CONSENT_LOG).strip(), args.purge_older_than_days)
        except OSError as exc:
            log("очистка не выполнена: " + type(exc).__name__ + " " + clean(exc.strerror or "", 80))
            return 1
        return 0

    try:
        cfg = Config(dict(os.environ))
    except ConfigError as exc:
        log("ошибка настройки: " + str(exc))
        return 2
    store = ConsentLog(cfg.consent_log)
    try:
        store.check()
    except OSError as exc:
        log("нет доступа к файлу записей о согласии " + cfg.consent_log + ": " + clean(exc.strerror or "", 80))
        return 2
    try:
        server = LeadServer(("127.0.0.1", cfg.port), cfg, store)
    except OSError as exc:
        log("не удалось занять 127.0.0.1:%d: %s" % (cfg.port, clean(exc.strerror or "", 80)))
        return 2

    def stop(signum: int, frame: object) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log("запущен: 127.0.0.1:%d, почта %s:%d (%s), получатели: %s, записи о согласии: %s, не больше %d заявок в час"
        % (cfg.port, cfg.smtp_host, cfg.smtp_port, "SSL" if cfg.smtp_ssl else "без шифрования, тест",
           ", ".join(cfg.mail_to), cfg.consent_log, cfg.max_per_hour))
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
    # новые соединения уже не принимаются; заявки, которые сейчас отправляются, дописываем до конца
    busy = [t for t in threading.enumerate() if t is not threading.current_thread() and not t.daemon]
    if busy:
        log("остановка: дожидаемся запросов в обработке: %d" % len(busy))
        for thread in busy:
            thread.join()
    log("остановлен")
    return 0


if __name__ == "__main__":
    sys.exit(main())
