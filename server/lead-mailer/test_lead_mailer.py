#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Локальная проверка lead_mailer.py — только стандартная библиотека, без сети и без настоящей почты.

    python test_lead_mailer.py

Поднимает на 127.0.0.1 поддельный SMTP-сервер (EHLO, AUTH PLAIN/LOGIN, MAIL, RCPT, DATA, QUIT — обычный TCP,
поэтому приёмник запускается с SMTP_SSL=0; один тест поднимает его за TLS с тестовым сертификатом и проверяет
рабочий путь SMTP_SSL=1), запускает lead_mailer.py отдельным процессом с тестовыми настройками и шлёт ему
заявки по HTTP. Проверки сроков (медленная почта, медленное тело запроса, остановка) идут на копии приёмника
внутри процесса теста с укороченными сроками.
"""
from __future__ import annotations

import base64
import datetime as dt
import email
import email.policy
import http.client
import importlib.util
import json
import os
import re
import socket
import socketserver
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest

sys.dont_write_bytecode = True  # копии модуля внутри теста не оставляют __pycache__ в папке, которую копируют на сервер

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "lead_mailer.py")
NGINX_SNIPPET = os.path.join(HERE, "nginx-api-lead.conf")
PY = [sys.executable, "-X", "utf8", "-I"]

SMTP_USER = "site@qodex.tech"
SMTP_PASSWORD = "test-app-password"
MAIL_TO = "info@qodex.tech"  # значение по умолчанию: в окружении теста MAIL_TO не задаём

EXPECTED_HEADERS = {
    "subject", "from", "to", "date", "message-id", "auto-submitted",
    "mime-version", "content-type", "content-transfer-encoding",
}

# Тестовый удостоверяющий центр и сертификат «localhost» / 127.0.0.1 (ECDSA P-256), выпущены 08.10.2026
# на 100 лет — только для test_17_ssl. Расширения как у настоящих сертификатов (CA:TRUE + keyUsage у центра,
# serverAuth + SAN + AKI у сервера), чтобы проверка проходила и в строгом режиме Python 3.13+.
TEST_CA_PEM = """-----BEGIN CERTIFICATE-----
MIIBrjCCAVWgAwIBAgIUQgjlKEd88uiTbVk5vrGucsa1b4owCgYIKoZIzj0EAwIw
JDEiMCAGA1UEAwwZUU9ERVggbGVhZC1tYWlsZXIgdGVzdCBDQTAgFw0yNjEwMDgw
NjU3NTdaGA8yMTI2MDkxNDA2NTc1N1owJDEiMCAGA1UEAwwZUU9ERVggbGVhZC1t
YWlsZXIgdGVzdCBDQTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABJlO/VruMP7+
Rk5wGxDcuUOXw0aJHsdr25tnHp5UzfBa5NouoEWUxEYrXLSZG9Hto6//p+YrvG7B
1rvH5nw2t+ujYzBhMB8GA1UdIwQYMBaAFKSUkXPHexyK6WctPcXHdb+Gz1fnMA8G
A1UdEwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMB0GA1UdDgQWBBSklJFzx3sc
iulnLT3Fx3W/hs9X5zAKBggqhkjOPQQDAgNHADBEAiEAyVOOcB7F1z+LpGreYX8F
VBzq4qgYgAVP+CdQ5YQ79c0CH1pqidcET07eKFpx88mku9lLY8sPQjc4APey4pPy
5pc=
-----END CERTIFICATE-----
"""
TEST_SERVER_CERT_PEM = """-----BEGIN CERTIFICATE-----
MIIBzjCCAXWgAwIBAgIUSiRfEqvvoejwqHtCclbz57YhuocwCgYIKoZIzj0EAwIw
JDEiMCAGA1UEAwwZUU9ERVggbGVhZC1tYWlsZXIgdGVzdCBDQTAgFw0yNjEwMDgw
NjU3NTdaGA8yMTI2MDkxNDA2NTc1N1owFDESMBAGA1UEAwwJbG9jYWxob3N0MFkw
EwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE6Lb/G/xPAXNCXU7LzTlgHSxu7nICiJ+b
s98NEp2Z8CFk9HWo2j2CXETY918IWFI2HfF+Ea+Z4eLs9ApQOcbJSKOBkjCBjzAM
BgNVHRMBAf8EAjAAMA4GA1UdDwEB/wQEAwIHgDATBgNVHSUEDDAKBggrBgEFBQcD
ATAaBgNVHREEEzARgglsb2NhbGhvc3SHBH8AAAEwHQYDVR0OBBYEFIKjlutoECQY
VbNGBGZPzU5qt/VfMB8GA1UdIwQYMBaAFKSUkXPHexyK6WctPcXHdb+Gz1fnMAoG
CCqGSM49BAMCA0cAMEQCIEXjPNxdFTPeMDd6oeZ2mj4gweg2Bah7CAHxP6BM38IM
AiB03dK43b9ty0tvtUzzWpC7fVuJxqsYMwifIgmUAaojEg==
-----END CERTIFICATE-----
"""
TEST_SERVER_KEY_PEM = """-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg5cyMcH72nrYUCEcR
gi9AwouGVGj9A7RWdaKSuZP5CFOhRANCAATotv8b/E8Bc0JdTsvNOWAdLG7ucgKI
n5uz3w0SnZnwIWT0dajaPYJcRNj3XwhYUjYd8X4Rr5nh4uz0ClA5xslI
-----END PRIVATE KEY-----
"""

# телефоны, которые форма сайта пропускает (в строке не меньше 10 цифр), — приёмник обязан их принять
FORM_PHONES = {
    "8 (999) 123-45-67 доб. 5": "Телефон: +79991234567 доб. 5 (введено: 8 (999) 123-45-67 доб. 5)",
    "+7 999 123 45 67 #12": "Телефон: +79991234567 доб. 12 (введено: +7 999 123 45 67 #12)",
    "+7 999 123\u201345\u201367": "Телефон: +79991234567 (введено: +7 999 123\u201345\u201367)",
    "+7\u2011999\u2011123\u201145\u201167": "Телефон: +79991234567 (введено: +7\u2011999\u2011123\u201145\u201167)",
    "+7/999/123/45/67": "Телефон: +79991234567 (введено: +7/999/123/45/67)",
    "+7 999 123-45-67, Иван": "Телефон: +79991234567 (введено: +7 999 123-45-67, Иван)",
    "8-999-123-45-67;": "Телефон: +79991234567 (введено: 8-999-123-45-67;)",
    "8 800 555-35-35 ДОБ 1234": "Телефон: +78005553535 доб. 1234 (введено: 8 800 555-35-35 ДОБ 1234)",
    "тел. 8 999 123 45 67": "Телефон: +79991234567 (введено: тел. 8 999 123 45 67)",
    "+44 20 7946 0958 ext. 12": "Телефон: +442079460958 доб. 12 (введено: +44 20 7946 0958 ext. 12)",
    "+79991234567": "Телефон: +79991234567\n",
}


# ---------------------------------------------------------------------------------------------------------------
# Поддельный SMTP-сервер


class FakeSMTPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 128

    def __init__(self, tls: "ssl.SSLContext | None" = None) -> None:
        super().__init__(("127.0.0.1", 0), FakeSMTPHandler)
        self.tls = tls
        self.messages = []  # {"from", "rcpts", "data"}
        self.fail_mode = None  # None | "auth" | "mail" | "data"
        self.reply_delay = 0.0  # пауза перед каждым ответом (медленный почтовый сервер)
        self.data_end_delay = 0.0  # пауза перед ответом на конец письма
        self.data_started = threading.Event()
        self.tls_failures = 0
        self.lock = threading.Lock()

    @property
    def port(self) -> int:
        return self.server_address[1]

    def count(self) -> int:
        with self.lock:
            return len(self.messages)

    def get_request(self):
        sock, addr = super().get_request()
        if self.tls is not None:  # рукопожатие — в потоке обработчика, чтобы не задерживать приём соединений
            sock = self.tls.wrap_socket(sock, server_side=True, do_handshake_on_connect=False)
        return sock, addr

    def handle_error(self, request, client_address) -> None:
        pass  # клиент ушёл по таймауту и т. п. — для теста это нормально


def start_smtp(tls=None) -> FakeSMTPServer:
    srv = FakeSMTPServer(tls)
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    return srv


def stop_smtp(srv: FakeSMTPServer) -> None:
    srv.shutdown()
    srv.server_close()


class FakeSMTPHandler(socketserver.StreamRequestHandler):
    timeout = 10

    def setup(self) -> None:
        if isinstance(self.request, ssl.SSLSocket):
            self.request.settimeout(self.timeout)
            try:
                self.request.do_handshake()
            except (ssl.SSLError, OSError):
                with self.server.lock:  # type: ignore[attr-defined]
                    self.server.tls_failures += 1  # type: ignore[attr-defined]
                self.handshake_failed = True
        super().setup()

    def pause(self) -> None:
        delay = self.server.reply_delay  # type: ignore[attr-defined]
        if delay:
            time.sleep(delay)

    def say(self, line: str) -> None:
        self.pause()
        self.wfile.write(line.encode("ascii") + b"\r\n")
        self.wfile.flush()

    def read_line(self) -> str:
        return self.rfile.readline(65536).decode("utf-8", "replace").rstrip("\r\n")

    @staticmethod
    def b64(text: str) -> str:
        return base64.b64decode(text.strip()).decode("utf-8")

    def handle(self) -> None:
        if getattr(self, "handshake_failed", False):
            return
        srv: FakeSMTPServer = self.server  # type: ignore[assignment]
        authed = False
        mail_from = None
        rcpts = []
        self.say("220 fake.smtp ESMTP ready")
        while True:
            raw = self.rfile.readline(65536)
            if not raw:
                return
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            cmd, _, arg = line.partition(" ")
            cmd = cmd.upper()
            if cmd == "EHLO":
                self.pause()
                self.wfile.write(b"250-fake.smtp\r\n250-AUTH PLAIN LOGIN\r\n250-8BITMIME\r\n250 SIZE 1000000\r\n")
                self.wfile.flush()
            elif cmd == "HELO":
                self.say("250 fake.smtp")
            elif cmd == "AUTH":
                mech, _, initial = arg.partition(" ")
                mech = mech.upper()
                try:
                    if mech == "PLAIN":
                        if not initial:
                            self.say("334 ")
                            initial = self.read_line()
                        _, user, password = base64.b64decode(initial).decode("utf-8").split("\0")
                    elif mech == "LOGIN":
                        if initial:
                            user = self.b64(initial)
                        else:
                            self.say("334 VXNlcm5hbWU6")
                            user = self.b64(self.read_line())
                        self.say("334 UGFzc3dvcmQ6")
                        password = self.b64(self.read_line())
                    else:
                        self.say("504 5.5.4 Unrecognized authentication type")
                        continue
                except Exception:
                    self.say("501 5.5.2 Cannot decode")
                    continue
                if srv.fail_mode != "auth" and (user, password) == (SMTP_USER, SMTP_PASSWORD):
                    authed = True
                    self.say("235 2.7.0 Authentication successful")
                else:
                    self.say("535 5.7.8 Authentication credentials invalid")
            elif cmd == "MAIL":
                if not authed:
                    self.say("530 5.7.0 Authentication required")
                elif srv.fail_mode == "mail":
                    self.say("451 4.3.0 Temporary local problem")
                else:
                    mail_from = arg.split(":", 1)[1].strip().split()[0].strip("<>")
                    rcpts = []
                    self.say("250 2.1.0 OK")
            elif cmd == "RCPT":
                if mail_from is None:
                    self.say("503 5.5.1 MAIL first")
                else:
                    rcpts.append(arg.split(":", 1)[1].strip().split()[0].strip("<>"))
                    self.say("250 2.1.5 OK")
            elif cmd == "DATA":
                if not rcpts:
                    self.say("503 5.5.1 RCPT first")
                    continue
                srv.data_started.set()
                self.say("354 End data with <CR><LF>.<CR><LF>")
                chunks = []
                while True:
                    part = self.rfile.readline()
                    if not part:
                        return
                    if part in (b".\r\n", b".\n"):
                        break
                    if part.startswith(b".."):
                        part = part[1:]
                    chunks.append(part)
                if srv.data_end_delay:
                    time.sleep(srv.data_end_delay)
                if srv.fail_mode == "data":
                    self.say("554 5.6.0 Message rejected")
                else:
                    with srv.lock:
                        srv.messages.append({"from": mail_from, "rcpts": list(rcpts), "data": b"".join(chunks)})
                    self.say("250 2.0.0 OK queued")
                mail_from, rcpts = None, []
            elif cmd == "RSET":
                mail_from, rcpts = None, []
                self.say("250 2.0.0 OK")
            elif cmd == "NOOP":
                self.say("250 2.0.0 OK")
            elif cmd == "QUIT":
                self.say("221 2.0.0 Bye")
                return
            else:
                self.say("502 5.5.2 Command not recognized")


# ---------------------------------------------------------------------------------------------------------------
# Помощники


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def mailer_env(smtp_port: int, port: int, consent_log: str, **extra: str) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("SMTP_", "MAIL_", "CONSENT_", "SSL_CERT_", "MAX_LEADS_"))}
    env.pop("PORT", None)
    env.update({
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": str(smtp_port),
        "SMTP_SSL": "0",
        "SMTP_USER": SMTP_USER,
        "SMTP_PASSWORD": SMTP_PASSWORD,
        "PORT": str(port),
        "CONSENT_LOG": consent_log,
        # общий потолок поднят: тесты шлют больше 30 заявок; значение по умолчанию проверяет test_25
        "MAX_LEADS_PER_HOUR": "1000",
    })
    env.update(extra)
    return env


def start_mailer(env: dict, log_path: str) -> subprocess.Popen:
    log_file = open(log_path, "ab")
    proc = subprocess.Popen(PY + [SCRIPT], env=env, stdout=log_file, stderr=log_file)
    log_file.close()
    port = int(env["PORT"])
    deadline = time.time() + 15
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError("lead_mailer.py завершился при запуске:\n" + read_text(log_path))
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc
        except OSError:
            time.sleep(0.1)
    proc.kill()
    raise RuntimeError("lead_mailer.py не начал слушать порт")


def stop_mailer(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def load_mailer_module():
    """Отдельная копия модуля lead_mailer: её сроки можно укоротить, не трогая другие тесты."""
    spec = importlib.util.spec_from_file_location("lead_mailer_copy_%d" % time.monotonic_ns(), SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class InProcessMailer:
    """Приёмник внутри процесса теста. `constants` подменяют сроки модуля (BODY_DEADLINE, SMTP_TIMEOUT …)."""

    def __init__(self, smtp_port: int, consent_log: str, **constants: object) -> None:
        self.mod = load_mailer_module()
        for name, value in constants.items():
            assert hasattr(self.mod, name), name
            setattr(self.mod, name, value)
        self.logs = []
        self.mod.log = self.logs.append  # строки журнала — в список, а не в вывод теста
        cfg = self.mod.Config(mailer_env(smtp_port, free_port(), consent_log))
        store = self.mod.ConsentLog(consent_log)
        store.check()
        self.server = self.mod.LeadServer(("127.0.0.1", cfg.port), cfg, store)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                                       daemon=True)
        self.thread.start()

    def close(self) -> None:
        if self.thread.is_alive():
            self.server.shutdown()
        self.server.server_close()


def read_text(path: str) -> str:
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except FileNotFoundError:
        return ""


def consent_lines(path: str) -> list:
    return [json.loads(l) for l in read_text(path).splitlines() if l.strip()]


def lead(**overrides) -> dict:
    payload = {
        "name": "Иван Петров",
        "phone": "+7 (999) 123-45-67",
        "interest": ["tracker", "robot"],  # порядок нарочно не тот: в письме — порядок продуктов сайта
        "trackerDemo": True,
        "utm": {"utm_source": "yandex", "utm_campaign": "осень-тко"},
        "page": "https://qodex.tech/tracker/?utm_source=yandex&yclid=5550123456789#lead",
        "sentAt": "2026-10-09T09:34:56.789Z",
        "consent": {"given": True, "edition": "09.10.2026", "text": "https://qodex.tech/consent/"},
    }
    payload.update(overrides)
    return payload


_ip_counter = [0]


def next_ip() -> str:
    """Каждый раз новый адрес (у каждого — свой лимит 5 заявок за 10 минут)."""
    _ip_counter[0] += 1
    n = _ip_counter[0]
    return "203.0.113.%d" % n if n <= 254 else "198.18.%d.%d" % divmod(n, 256)


def raw_post(port: int, head_length: int, body: bytes) -> socket.socket:
    """Начать POST вручную: заголовки с заявленной длиной и первые байты тела."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=30)
    sock.sendall(("POST /api/lead HTTP/1.1\r\nHost: test\r\nContent-Type: application/json\r\n"
                  "X-Real-IP: %s\r\nContent-Length: %d\r\n\r\n" % (next_ip(), head_length)).encode("ascii") + body)
    return sock


def read_status(sock: socket.socket) -> int:
    data = b""
    while b"\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data += chunk
    return int(data.split(b" ", 2)[1]) if data else 0


# ---------------------------------------------------------------------------------------------------------------
# Тесты


class LeadMailerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="lead-mailer-test-")
        cls.consent_log = os.path.join(cls.tmp.name, "consent.jsonl")
        cls.log_path = os.path.join(cls.tmp.name, "mailer.log")
        cls.smtp = start_smtp()
        cls.port = free_port()
        cls.proc = start_mailer(mailer_env(cls.smtp.port, cls.port, cls.consent_log), cls.log_path)

    @classmethod
    def tearDownClass(cls) -> None:
        stop_mailer(cls.proc)
        stop_smtp(cls.smtp)
        cls.tmp.cleanup()

    # --- запросы

    def request(self, method="POST", path="/api/lead", body=None, ctype="application/json; charset=utf-8",
                ip=None, port=None):
        conn = http.client.HTTPConnection("127.0.0.1", port or self.port, timeout=60)
        headers = {"X-Real-IP": ip or next_ip()}
        if ctype:
            headers["Content-Type"] = ctype
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        try:
            conn.request(method, path, body=body, headers=headers)
            res = conn.getresponse()
            raw = res.read()
        finally:
            conn.close()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else None
        except ValueError:
            data = raw
        return res.status, data, res

    def assert_rejected(self, status, body, expected_status, smtp=None, consent_log=None, **req):
        smtp = smtp or self.smtp
        consent_log = consent_log or self.consent_log
        mails, consents = smtp.count(), len(consent_lines(consent_log))
        got, data, _ = self.request(body=body, **req)
        self.assertEqual(got, expected_status, data)
        self.assertEqual(smtp.count(), mails, "письмо не должно уходить")
        self.assertEqual(len(consent_lines(consent_log)), consents, "запись о согласии не должна появляться")
        return data

    def last_mail(self, smtp=None):
        smtp = smtp or self.smtp
        with smtp.lock:
            item = smtp.messages[-1]
        return item, email.message_from_bytes(item["data"], policy=email.policy.default)

    def parallel(self, payloads_and_ips, port=None):
        """Одновременные заявки: [(payload, ip), …] → список кодов ответа (или имён исключений)."""
        results = [None] * len(payloads_and_ips)
        barrier = threading.Barrier(len(payloads_and_ips))

        def worker(i, payload, ip):
            barrier.wait()
            try:
                results[i] = self.request(body=payload, ip=ip, port=port)[0]
            except Exception as exc:  # отказ в соединении и т. п.
                results[i] = type(exc).__name__

        threads = [threading.Thread(target=worker, args=(i, p, ip)) for i, (p, ip) in enumerate(payloads_and_ips)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(120)
        return results

    # --- сценарии

    def test_01_valid_lead(self):
        mails, consents = self.smtp.count(), len(consent_lines(self.consent_log))
        before = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        status, data, res = self.request(body=lead())
        self.assertEqual(status, 200)
        self.assertEqual(data, {"ok": True})
        self.assertTrue(res.getheader("Content-Type").startswith("application/json"))

        self.assertEqual(self.smtp.count(), mails + 1, "ровно одно письмо")
        item, msg = self.last_mail()
        self.assertEqual(item["from"], SMTP_USER)
        self.assertEqual(item["rcpts"], [MAIL_TO])
        self.assertEqual(msg["Subject"], "Заявка с сайта qodex.tech: РО-БОТ, QODEX Tracker")
        self.assertEqual(msg["From"].addresses[0].addr_spec, SMTP_USER)
        self.assertEqual(msg["From"].addresses[0].display_name, "Сайт qodex.tech")
        self.assertEqual(str(msg["To"]), MAIL_TO)
        self.assertEqual(msg.get_content_type(), "text/plain")
        self.assertEqual(msg.get_content_charset(), "utf-8")
        body = msg.get_content()
        for expected in (
            "Имя: Иван Петров",
            "Телефон: +79991234567 (введено: +7 (999) 123-45-67)",
            "Интересует: РО-БОТ, QODEX Tracker",
            "Tracker: запрос демо (пилот не обещаем)",
            "Страница: https://qodex.tech/tracker/?utm_source=yandex&yclid=5550123456789#lead",
            "UTM: utm_source=yandex; utm_campaign=осень-тко",
            "Отправлено: 09.10.2026 12:34:56 МСК (время браузера)",
            "Согласие на обработку персональных данных: дано, редакция от 09.10.2026, "
            "текст: https://qodex.tech/consent/",
        ):
            self.assertIn(expected, body)
        received_line = [l for l in body.splitlines() if l.startswith("Получено: ")]
        self.assertEqual(len(received_line), 1)
        self.assertRegex(received_line[0],
                         r"^Получено: \d\d\.\d\d\.\d{4} \d\d:\d\d:\d\d МСК / \d\d\.\d\d\.\d{4} \d\d:\d\d:\d\d UTC "
                         r"\(время сервера\)$")

        lines = consent_lines(self.consent_log)
        self.assertEqual(len(lines), consents + 1, "ровно одна запись о согласии")
        rec = lines[-1]
        self.assertEqual(set(rec), {"received_at", "phone", "consent_given", "consent_edition", "consent_text",
                                    "page"})
        self.assertEqual(rec["phone"], "+79991234567")
        self.assertIs(rec["consent_given"], True)
        self.assertEqual(rec["consent_edition"], "09.10.2026")
        self.assertEqual(rec["consent_text"], "https://qodex.tech/consent/")
        # страница без строки запроса и якоря: метки рекламы (yclid) рядом с телефоном не храним
        self.assertEqual(rec["page"], "https://qodex.tech/tracker/")
        self.assertNotIn("yclid", read_text(self.consent_log))
        received = dt.datetime.strptime(rec["received_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        self.assertLessEqual(abs((received - before).total_seconds()), 10)
        self.assertNotIn("name", rec, "имя в записи о согласии не нужно")
        if os.name == "posix":
            self.assertEqual(os.stat(self.consent_log).st_mode & 0o777, 0o600)

    def test_02_no_product(self):
        status, data, _ = self.request(body=lead(interest=[], trackerDemo=False, utm={}, page=None))
        self.assertEqual(status, 200, data)
        _, msg = self.last_mail()
        self.assertEqual(msg["Subject"], "Заявка с сайта qodex.tech: продукт не выбран")
        body = msg.get_content()
        self.assertIn("Интересует: продукт не выбран", body)
        self.assertNotIn("Tracker:", body)
        self.assertIn("UTM: нет", body)
        self.assertIn("Страница: не указана", body)
        self.assertEqual(consent_lines(self.consent_log)[-1]["page"], "")

    def test_03_invalid_phone(self):
        for phone in ("12345", "+7 999 123", "+1234567890123456", "телефон", "1-2-3-4-5-6-7-8-9",
                      "8 999 123 45 67 8 999 765 43 21", 79991234567, None, ""):
            with self.subTest(phone=phone):
                data = self.assert_rejected(None, lead(phone=phone), 400)
                self.assertEqual(data, {"ok": False, "error": "phone"})

    def test_03b_form_phone_formats(self):
        # всё, что пропускает форма сайта (не меньше 10 цифр), с добавочным, тире, дробью, подписью — принимается
        for phone, line in FORM_PHONES.items():
            with self.subTest(phone=phone):
                consents = len(consent_lines(self.consent_log))
                status, data, _ = self.request(body=lead(phone=phone))
                self.assertEqual(status, 200, data)
                body = self.last_mail()[1].get_content()
                self.assertIn(line, body)
                rec = consent_lines(self.consent_log)
                self.assertEqual(len(rec), consents + 1)
                # в записи о согласии — нормализованный основной номер, без добавочного и подписей
                self.assertRegex(rec[-1]["phone"], r"^\+\d{10,15}$")
                self.assertEqual(rec[-1]["phone"], line.split()[1])

    def test_04_no_consent(self):
        no_consent = lead()
        del no_consent["consent"]
        cases = [
            no_consent,
            lead(consent=None),
            lead(consent={"given": False, "edition": "09.10.2026", "text": "https://qodex.tech/consent/"}),
            lead(consent={"given": "true", "edition": "09.10.2026", "text": "https://qodex.tech/consent/"}),
            lead(consent={"given": True, "text": "https://qodex.tech/consent/"}),
            lead(consent={"given": True, "edition": "x" * 21, "text": "https://qodex.tech/consent/"}),
            lead(consent={"given": True, "edition": "09.10.2026"}),
            lead(consent={"given": True, "edition": "09.10.2026", "text": "javascript:alert(1)"}),
        ]
        for i, payload in enumerate(cases):
            with self.subTest(case=i):
                data = self.assert_rejected(None, payload, 400)
                self.assertEqual(data["error"], "consent")

    def test_05_invalid_name_and_interest(self):
        for name in ("", "   ", "\r\n\t", "я" * 101, None, 42):
            with self.subTest(name=name):
                self.assertEqual(self.assert_rejected(None, lead(name=name), 400)["error"], "name")
        for interest in (["crm"], "robot", ["robot", 1], {"robot": True}):
            with self.subTest(interest=interest):
                self.assertEqual(self.assert_rejected(None, lead(interest=interest), 400)["error"], "interest")
        self.assertEqual(self.assert_rejected(None, [lead()], 400)["error"], "body")

    def test_06_invalid_json(self):
        self.assert_rejected(None, b'{"name": "x",', 400)
        self.assert_rejected(None, "{}".encode("utf-16"), 400)
        self.assert_rejected(None, b"[" * 5000 + b"]" * 5000, 400)

    def test_07_oversize(self):
        payload = lead(padding="x" * (20 * 1024))
        data = self.assert_rejected(None, payload, 413)
        self.assertEqual(data, {"ok": False, "error": "too_large"})

    def test_08_wrong_content_type(self):
        body = json.dumps(lead()).encode()
        for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data; boundary=x", None):
            with self.subTest(ctype=ctype):
                self.assert_rejected(None, body, 415, ctype=ctype)

    def test_09_methods_and_paths(self):
        for method in ("GET", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"):
            with self.subTest(method=method):
                status, _, res = self.request(method=method, body=None, ctype=None)
                self.assertEqual(status, 405)
                self.assertEqual(res.getheader("Allow"), "POST")
        for method, path in (("GET", "/"), ("POST", "/api/lead/"), ("POST", "/api/leads"), ("GET", "/api/other")):
            with self.subTest(path=path):
                body = lead() if method == "POST" else None
                self.assertEqual(self.request(method=method, path=path, body=body)[0], 404)
        self.assertEqual(self.request(path="/api/lead?x=1", body=lead())[0], 200, "строка запроса не мешает")

    def test_10_header_injection(self):
        mails = self.smtp.count()
        payload = lead(
            name="Иван\r\nBcc: evil@example.com\r\nSubject: hacked",
            phone="+7 999 123-45-67",
            utm={"utm_source": "x\r\nBcc: evil2@example.com", "utm_x\r\nBcc": "evil3@example.com", "bcc": "y"},
            page="https://qodex.tech/\r\nBcc: evil4@example.com",
            sentAt="2026-10-09T09:34:56Z\nBcc: evil5@example.com",
        )
        payload["consent"]["edition"] = "09.10\r\n.2026"
        status, data, _ = self.request(body=payload)
        self.assertEqual(status, 200, data)
        self.assertEqual(self.smtp.count(), mails + 1)
        item, msg = self.last_mail()
        self.assertEqual(item["rcpts"], [MAIL_TO], "лишних получателей нет")
        self.assertEqual({k.lower() for k in msg.keys()}, EXPECTED_HEADERS, "лишних заголовков нет")
        self.assertIsNone(msg["Bcc"])
        self.assertEqual(msg["Subject"], "Заявка с сайта qodex.tech: РО-БОТ, QODEX Tracker")
        head = item["data"].split(b"\r\n\r\n", 1)[0]
        self.assertNotIn(b"evil", head)
        self.assertNotIn(b"hacked", head)
        body = msg.get_content()
        self.assertIn("Имя: Иван Bcc: evil@example.com Subject: hacked", body)
        self.assertIn("Страница: https://qodex.tech/ Bcc: evil4@example.com", body)
        self.assertIn("UTM: utm_source=x Bcc: evil2@example.com", body)
        self.assertNotIn("evil3", body, "ключ UTM с переводом строки отброшен")
        self.assertIn("редакция от 09.10 .2026", body)
        for line in body.splitlines():
            self.assertFalse(line.lower().startswith(("bcc:", "subject:")), line)
        rec = consent_lines(self.consent_log)[-1]
        self.assertEqual(rec["page"], "https://qodex.tech/ Bcc: evil4@example.com")
        self.assertNotIn("\n", json.dumps(rec, ensure_ascii=False))

    def test_11_rate_limit(self):
        ip = next_ip()
        for _ in range(3):  # отклонённые заявки лимит не расходуют
            self.assert_rejected(None, lead(phone="1"), 400, ip=ip)
        for i in range(5):
            status, data, _ = self.request(body=lead(), ip=ip)
            self.assertEqual(status, 200, "заявка %d" % (i + 1))
        data = self.assert_rejected(None, lead(), 429, ip=ip)
        self.assertEqual(data, {"ok": False, "error": "rate_limited"})
        _, _, res = self.request(body=lead(), ip=ip)
        self.assertGreater(int(res.getheader("Retry-After")), 500)
        self.assertEqual(self.request(body=lead(), ip=next_ip())[0], 200, "другой адрес не ограничен")

    def test_11b_rate_limit_ipv6_and_mapped(self):
        # 12 адресов одной сети IPv6 /64 — это один хост: принимаются 5 заявок, остальные 429
        codes = [self.request(body=lead(), ip="2001:db8:1:2::%x" % i)[0] for i in range(1, 13)]
        self.assertEqual(codes, [200] * 5 + [429] * 7)
        self.assertEqual(self.request(body=lead(), ip="2001:db8:1:2:ffff:ffff:ffff:ffff")[0], 429)
        self.assertEqual(self.request(body=lead(), ip="2001:db8:1:3::1")[0], 200, "соседняя /64 — другой хост")
        # IPv4, записанный как IPv6 (::ffff:a.b.c.d), — тот же адрес IPv4
        codes = [self.request(body=lead(), ip=ip)[0]
                 for ip in ("::ffff:198.51.100.77", "198.51.100.77") * 3]
        self.assertEqual(codes, [200] * 5 + [429])

    def test_12_smtp_rejects(self):
        ip = next_ip()
        for mode in ("auth", "mail", "data"):
            with self.subTest(mode=mode):
                self.smtp.fail_mode = mode
                try:
                    data = self.assert_rejected(None, lead(), 502, ip=ip)
                finally:
                    self.smtp.fail_mode = None
                self.assertEqual(data["ok"], False)
        # три неудачные отправки не отняли попыток: с того же адреса проходят ещё пять заявок
        for _ in range(5):
            self.assertEqual(self.request(body=lead(), ip=ip)[0], 200)

    def test_13_smtp_down(self):
        consent_log = os.path.join(self.tmp.name, "consent-down.jsonl")
        log_path = os.path.join(self.tmp.name, "mailer-down.log")
        port = free_port()
        proc = start_mailer(mailer_env(free_port(), port, consent_log), log_path)  # на этом порту SMTP нет
        try:
            status, data, _ = self.request(body=lead(), port=port)
            self.assertEqual(status, 502)
            self.assertEqual(data["ok"], False)
            self.assertEqual(consent_lines(consent_log), [], "без отправленного письма записи о согласии нет")
        finally:
            stop_mailer(proc)
        self.assertIn("502", read_text(log_path))

    def test_14_fail_fast_without_secrets(self):
        for missing in ("SMTP_USER", "SMTP_PASSWORD"):
            with self.subTest(missing=missing):
                env = mailer_env(1, free_port(), os.path.join(self.tmp.name, "c.jsonl"))
                env.pop(missing)
                done = subprocess.run(PY + [SCRIPT], env=env, capture_output=True, timeout=15)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn(missing, done.stderr.decode("utf-8"))
        env = mailer_env(1, free_port(), os.path.join(self.tmp.name, "c.jsonl"), SMTP_HOST="smtp.mail.ru")
        done = subprocess.run(PY + [SCRIPT], env=env, capture_output=True, timeout=15)
        self.assertNotEqual(done.returncode, 0, "SMTP_SSL=0 к внешнему серверу запрещён")
        self.assertIn("SMTP_SSL=0", done.stderr.decode("utf-8"))
        for value in ("abc", "0"):
            with self.subTest(MAX_LEADS_PER_HOUR=value):
                env = mailer_env(1, free_port(), os.path.join(self.tmp.name, "c.jsonl"), MAX_LEADS_PER_HOUR=value)
                done = subprocess.run(PY + [SCRIPT], env=env, capture_output=True, timeout=15)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn("MAX_LEADS_PER_HOUR", done.stderr.decode("utf-8"))

    def test_15_purge(self):
        path = os.path.join(self.tmp.name, "purge.jsonl")
        now = dt.datetime.now(dt.timezone.utc)

        def rec(days_ago):
            when = (now - dt.timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
            return json.dumps({"received_at": when, "phone": "+7900000%04d" % days_ago, "consent_given": True,
                               "consent_edition": "09.10.2026", "consent_text": "https://qodex.tech/consent/",
                               "page": "https://qodex.tech/"}, ensure_ascii=False)

        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join([rec(1200), rec(1096), rec(1000), "не JSON", rec(0)]) + "\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("SMTP_", "MAIL_"))}
        env["CONSENT_LOG"] = path
        done = subprocess.run(PY + [SCRIPT, "--purge-older-than-days", "1095"], env=env, capture_output=True,
                              timeout=15)
        self.assertEqual(done.returncode, 0, done.stderr.decode("utf-8"))
        left = read_text(path).splitlines()
        self.assertEqual(len(left), 3)
        self.assertEqual([json.loads(l)["phone"] for l in left if l.startswith("{")], ["+79000001000", "+79000000000"])
        self.assertIn("не JSON", left)
        self.assertIn("удалено 2", done.stderr.decode("utf-8"))
        # без файла — не ошибка
        env["CONSENT_LOG"] = os.path.join(self.tmp.name, "nope.jsonl")
        done = subprocess.run(PY + [SCRIPT, "--purge-older-than-days", "1095"], env=env, capture_output=True,
                              timeout=15)
        self.assertEqual(done.returncode, 0)

    def test_16_odd_sent_at(self):
        for sent_at, shown in (("0001-01-01T00:00:00+05:00", "0001-01-01T00:00:00+05:00"),
                               ("9999-12-31T23:59:59Z", "9999-12-31T23:59:59Z"),
                               ("вчера", "вчера"), (None, "не указано"), (12, "не указано")):
            with self.subTest(sent_at=sent_at):
                status, data, _ = self.request(body=lead(sentAt=sent_at))
                self.assertEqual(status, 200, data)
                self.assertIn("Отправлено: " + shown + " (время браузера)", self.last_mail()[1].get_content())

    def test_17_ssl(self):
        # рабочий путь: SMTP_SSL=1, сертификат сервера проверяется по доверенным центрам и по имени
        ca = os.path.join(self.tmp.name, "test-ca.pem")
        cert = os.path.join(self.tmp.name, "test-server.pem")
        key = os.path.join(self.tmp.name, "test-server.key")
        for path, text in ((ca, TEST_CA_PEM), (cert, TEST_SERVER_CERT_PEM), (key, TEST_SERVER_KEY_PEM)):
            with open(path, "w", encoding="ascii", newline="\n") as f:
                f.write(text)
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cert, key)
        smtp = start_smtp(tls)
        try:
            # доверяем тестовому центру — письмо уходит, запись о согласии есть
            consent_log = os.path.join(self.tmp.name, "consent-ssl.jsonl")
            log_path = os.path.join(self.tmp.name, "mailer-ssl.log")
            port = free_port()
            env = mailer_env(smtp.port, port, consent_log, SMTP_SSL="1", SMTP_HOST="localhost", SSL_CERT_FILE=ca)
            proc = start_mailer(env, log_path)
            try:
                status, data, _ = self.request(body=lead(), port=port)
            finally:
                stop_mailer(proc)
            self.assertEqual(status, 200, read_text(log_path))
            self.assertEqual(smtp.count(), 1)
            self.assertEqual(self.last_mail(smtp)[1]["Subject"], "Заявка с сайта qodex.tech: РО-БОТ, QODEX Tracker")
            self.assertEqual(len(consent_lines(consent_log)), 1)
            self.assertIn("(SSL)", read_text(log_path))

            # без доверия к центру — сертификат не проходит проверку: 502, письма и записи о согласии нет
            consent_log = os.path.join(self.tmp.name, "consent-ssl-bad.jsonl")
            log_path = os.path.join(self.tmp.name, "mailer-ssl-bad.log")
            port = free_port()
            env = mailer_env(smtp.port, port, consent_log, SMTP_SSL="1", SMTP_HOST="localhost")
            proc = start_mailer(env, log_path)
            try:
                status, data, _ = self.request(body=lead(), port=port)
            finally:
                stop_mailer(proc)
            self.assertEqual(status, 502, data)
            self.assertEqual(smtp.count(), 1, "письмо не ушло")
            self.assertEqual(consent_lines(consent_log), [])
            self.assertIn("SSLCertVerificationError", read_text(log_path))
            self.assertGreaterEqual(smtp.tls_failures, 1)
        finally:
            stop_smtp(smtp)

    def test_18_parallel_same_ip(self):
        # 20 одновременных заявок с одного адреса: ровно 5 проходят, ровно 5 писем
        mails = self.smtp.count()
        ip = next_ip()
        codes = self.parallel([(lead(), ip)] * 20)
        self.assertEqual(sorted(codes, key=str), [200] * 5 + [429] * 15, codes)
        self.assertEqual(self.smtp.count(), mails + 5)

    def test_19_parallel_burst(self):
        # 60 одновременных заявок с разных адресов: все получают ответ 200, никто не получает отказ в соединении
        mails = self.smtp.count()
        codes = self.parallel([(lead(), next_ip()) for _ in range(60)])
        self.assertEqual(codes, [200] * 60, codes)
        self.assertEqual(self.smtp.count(), mails + 60)

    def test_20_slow_smtp(self):
        smtp = start_smtp()
        consent_log = os.path.join(self.tmp.name, "consent-slow.jsonl")
        mailer = InProcessMailer(smtp.port, consent_log, SMTP_TIMEOUT=1)
        try:
            # медленно, но в пределах SMTP_TIMEOUT на каждый ответ — письмо уходит
            smtp.reply_delay = 0.3
            status, data, _ = self.request(body=lead(), port=mailer.port)
            self.assertEqual(status, 200, mailer.logs)
            self.assertEqual(len(consent_lines(consent_log)), 1)
            # сервер не отвечает дольше SMTP_TIMEOUT — быстрый 502, без письма и без записи о согласии
            smtp.reply_delay = 1.5
            started = time.monotonic()
            data = self.assert_rejected(None, lead(), 502, smtp=smtp, consent_log=consent_log, port=mailer.port)
            self.assertLess(time.monotonic() - started, 3)
            self.assertEqual(data["error"], "mail")
        finally:
            mailer.close()
            smtp.reply_delay = 0
            stop_smtp(smtp)

    def test_21_timeouts_fit_nginx(self):
        # nginx ждёт ответ приёмника дольше, чем длится самая медленная отправка письма: иначе посетитель
        # увидит 504, письмо всё равно уйдёт, и повторная заявка даст второе письмо
        mod = load_mailer_module()
        with open(NGINX_SNIPPET, encoding="utf-8") as f:
            conf = f.read()
        read_timeout = int(re.search(r"^\s*proxy_read_timeout\s+(\d+)s;", conf, re.M).group(1))
        self.assertEqual(mod.SMTP_TIMEOUT, 10)
        self.assertGreaterEqual(mod.SMTP_WORST_CASE, mod.SMTP_TIMEOUT * 13)
        self.assertGreater(read_timeout, mod.SMTP_WORST_CASE)
        self.assertIn("limit_req zone=qodex_lead", conf)
        with open(os.path.join(HERE, "nginx-lead-limit.conf"), encoding="utf-8") as f:
            self.assertIn("zone=qodex_lead:", f.read())

    def test_22_body_deadlines(self):
        # слишком большое тело, которое не дослали: 413 (раньше — 500 через 20 с)
        started = time.monotonic()
        sock = raw_post(self.port, 100000, b"x" * 376)
        try:
            self.assertEqual(read_status(sock), 413)
        finally:
            sock.close()
        self.assertLess(time.monotonic() - started, 10)

        smtp = start_smtp()
        consent_log = os.path.join(self.tmp.name, "consent-body.jsonl")
        mailer = InProcessMailer(smtp.port, consent_log, BODY_DEADLINE=2, DRAIN_DEADLINE=1)
        try:
            # то же на копии с короткими сроками
            sock = raw_post(mailer.port, 100000, b"x" * 376)
            started = time.monotonic()
            try:
                self.assertEqual(read_status(sock), 413)
            finally:
                sock.close()
            self.assertLess(time.monotonic() - started, 2)
            self.assertFalse([l for l in mailer.logs if "внутренняя ошибка" in l], mailer.logs)

            # тело по байту раз в 0,25 с: каждое чтение укладывается в таймаут, но общий срок — 2 с → 408
            sock = raw_post(mailer.port, 200, b"{")
            stop = threading.Event()

            def drip():
                while not stop.wait(0.25):
                    try:
                        sock.sendall(b" ")
                    except OSError:
                        return

            dripper = threading.Thread(target=drip, daemon=True)
            started = time.monotonic()
            dripper.start()
            try:
                self.assertEqual(read_status(sock), 408)
            finally:
                stop.set()
                sock.close()
            self.assertLess(time.monotonic() - started, 4)

            # тело, присланное в два приёма с паузой, читается целиком
            body = json.dumps(lead(), ensure_ascii=False).encode("utf-8")
            sock = raw_post(mailer.port, len(body), body[:100])
            try:
                time.sleep(0.5)
                sock.sendall(body[100:])
                self.assertEqual(read_status(sock), 200)
            finally:
                sock.close()
            self.assertEqual(smtp.count(), 1)
        finally:
            mailer.close()
            stop_smtp(smtp)

    def test_23_consent_log_unavailable(self):
        consent_log = os.path.join(self.tmp.name, "consent-ro.jsonl")
        log_path = os.path.join(self.tmp.name, "mailer-ro.log")
        port = free_port()
        proc = start_mailer(mailer_env(self.smtp.port, port, consent_log), log_path)
        ip = next_ip()
        try:
            self.assertEqual(self.request(body=lead(), ip=ip, port=port)[0], 200)
            # файл записей о согласии стал недоступен для записи (на его месте — папка)
            os.remove(consent_log)
            os.mkdir(consent_log)
            mails = self.smtp.count()
            status, data, _ = self.request(body=lead(), ip=ip, port=port)
            self.assertEqual(status, 503)
            self.assertEqual(data, {"ok": False, "error": "storage"})
            self.assertEqual(self.smtp.count(), mails, "без возможности сохранить согласие письмо не уходит")
            # файл снова доступен — заявки принимаются; отказ 503 не отнял попытку у посетителя
            os.rmdir(consent_log)
            for _ in range(4):
                self.assertEqual(self.request(body=lead(), ip=ip, port=port)[0], 200)
            self.assertEqual(len(consent_lines(consent_log)), 4)
        finally:
            stop_mailer(proc)
        text = read_text(log_path)
        self.assertIn("ОШИБКА: CONSENT_LOG недоступен", text)
        self.assertIn("POST /api/lead 503", text)

    def test_24_stop_waits_and_threads_not_kept(self):
        mod = load_mailer_module()
        self.assertIs(mod.LeadServer.daemon_threads, False)
        self.assertIs(mod.LeadServer.block_on_close, False)
        self.assertGreaterEqual(mod.LeadServer.request_queue_size, 128)

        smtp = start_smtp()
        consent_log = os.path.join(self.tmp.name, "consent-stop.jsonl")
        mailer = InProcessMailer(smtp.port, consent_log)
        try:
            for _ in range(5):
                self.assertEqual(self.request(body=lead(), port=mailer.port)[0], 200)
            # сервер не копит потоки (bpo-37193: в Python 3.8 — 3.9.10 такой список рос без конца)
            kept = getattr(mailer.server, "_threads", None)
            self.assertFalse(isinstance(kept, list) and len(kept) > 0, kept)

            # остановка во время отправки: заявка дописывается, посетитель получает 200
            smtp.data_end_delay = 1.0
            smtp.data_started.clear()
            result = {}
            client = threading.Thread(
                target=lambda: result.update(status=self.request(body=lead(), port=mailer.port)[0]))
            client.start()
            self.assertTrue(smtp.data_started.wait(10))
            mailer.close()
            client.join(30)
            self.assertEqual(result.get("status"), 200)
            self.assertEqual(smtp.count(), 6)
            self.assertEqual(len(consent_lines(consent_log)), 6)
            with self.assertRaises(OSError):
                socket.create_connection(("127.0.0.1", mailer.port), timeout=2).close()
        finally:
            smtp.data_end_delay = 0
            stop_smtp(smtp)

    def test_25_total_limit(self):
        # значение по умолчанию: не больше 30 принятых заявок в час со всех адресов вместе
        consent_log = os.path.join(self.tmp.name, "consent-total.jsonl")
        log_path = os.path.join(self.tmp.name, "mailer-total.log")
        port = free_port()
        env = mailer_env(self.smtp.port, port, consent_log)
        env.pop("MAX_LEADS_PER_HOUR")
        proc = start_mailer(env, log_path)
        try:
            # неудачные отправки места в общем лимите не занимают
            self.smtp.fail_mode = "data"
            try:
                for _ in range(3):
                    self.assertEqual(self.request(body=lead(), port=port)[0], 502)
            finally:
                self.smtp.fail_mode = None
            mails = self.smtp.count()
            for n in range(6):  # 6 адресов × 5 заявок = 30
                ip = next_ip()
                for _ in range(5):
                    self.assertEqual(self.request(body=lead(), ip=ip, port=port)[0], 200, "адрес %d" % n)
            status, data, res = self.request(body=lead(), port=port)  # новый адрес, но общий потолок
            self.assertEqual(status, 429)
            self.assertEqual(data, {"ok": False, "error": "rate_limited"})
            self.assertGreater(int(res.getheader("Retry-After")), 3000)
            self.assertEqual(self.smtp.count(), mails + 30)
            self.assertEqual(len(consent_lines(consent_log)), 30)
        finally:
            stop_mailer(proc)
        self.assertIn("общий лимит", read_text(log_path))

    def test_26_client_gone_before_reply(self):
        # посетитель закрыл соединение, пока письмо отправлялось: заявка обработана, в журнале — не «внутренняя
        # ошибка», а «ответ не доставлен»
        smtp = start_smtp()
        consent_log = os.path.join(self.tmp.name, "consent-gone.jsonl")
        mailer = InProcessMailer(smtp.port, consent_log)
        try:
            smtp.data_end_delay = 0.5
            body = json.dumps(lead(), ensure_ascii=False).encode("utf-8")
            sock = raw_post(mailer.port, len(body), body)
            self.assertTrue(smtp.data_started.wait(10))
            # SO_LINGER с нулевым сроком: закрытие сразу обрывает соединение (struct linger в Windows — два short)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("HH" if os.name == "nt" else "ii", 1, 0))
            sock.close()  # RST: соединение оборвано
            deadline = time.monotonic() + 10
            while not any("200" in l for l in mailer.logs) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertEqual(smtp.count(), 1)
            self.assertEqual(len(consent_lines(consent_log)), 1)
            self.assertFalse([l for l in mailer.logs if "внутренняя ошибка" in l], mailer.logs)
            status_lines = [l for l in mailer.logs if l.startswith("POST /api/lead 200")]
            self.assertEqual(len(status_lines), 1, mailer.logs)
        finally:
            mailer.close()
            stop_smtp(smtp)

    def test_99_logs_have_no_personal_data(self):
        text = read_text(self.log_path)
        self.assertIn("POST /api/lead 200 заявка отправлена", text)
        self.assertIn("POST /api/lead 429 rate_limited", text)
        self.assertIn("POST /api/lead 413 too_large", text)
        self.assertNotIn("внутренняя ошибка", text)
        for secret in ("Иван", "Петров", "123-45-67", "79991234567", "203.0.113", "198.18.", "198.51.100", "2001:db8",
                       "yclid", SMTP_PASSWORD, "evil"):
            self.assertNotIn(secret, text, "в журнале не должно быть: " + secret)


if __name__ == "__main__":
    unittest.main(verbosity=2)
