#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Тесты weeek-bridge на поддельном Weeek (сеть не нужна): python3 test_weeek_bridge.py"""
import http.server
import json
import os
import socketserver
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
import weeek_bridge as wb  # noqa: E402

CONSENT = "Согласие на обработку персональных данных: дано, редакция от 09.10.2026, текст: https://qodex.tech/consent/"
COMMENT = "\nЧто интересно: РО-БОТ\nОткуда: окно заявки — кнопка «Запустить пилот»\nСтраница: https://qodex.tech/ro-bot/\n" + CONSENT


class FakeWeeek:
    """Поддельный Weeek: контакты в памяти, нечёткий поиск (как у настоящего), журнал вызовов, режим сбоя."""

    def __init__(self) -> None:
        self.contacts = [
            {"id": "c-old", "firstName": "Старый клиент", "phones": [{"id": "p1", "phone": "+79170000000"}], "emails": []},
            {"id": "c-other", "firstName": "Другой", "phones": [{"id": "p2", "phone": "+79991112233"}],
             "emails": [{"id": "e1", "email": "Boss@Example.ru"}]},
        ]
        self.deals = []
        self.calls = []
        self.fail_next = 0  # столько следующих запросов ответят 500
        self.fail_code = 500
        fake = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, code, body):
                data = json.dumps(body, ensure_ascii=False).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def handle_any(self, method):
                body = None
                if method == "POST":
                    body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.calls.append((method, self.path, body, self.headers.get("Authorization")))
                if fake.fail_next:
                    fake.fail_next -= 1
                    return self.send(fake.fail_code, {"error": "boom"})
                if method == "GET" and self.path.startswith("/crm/contacts?"):
                    # нечёткий поиск: первый контакт отдаётся всегда, плюс подходящие по подстроке
                    q = urllib.request.unquote(self.path.split("search=")[1]).lower()
                    hits = [c for c in fake.contacts if q in json.dumps(c, ensure_ascii=False).lower()]
                    return self.send(200, {"success": True, "contacts": [fake.contacts[0]] + hits})
                if method == "POST" and self.path == "/crm/contacts":
                    c = {"id": f"c-new-{len(fake.contacts)}", "firstName": body["firstName"],
                         "phones": [{"phone": p} for p in body.get("phones", [])],
                         "emails": [{"email": e} for e in body.get("emails", [])]}
                    fake.contacts.append(c)
                    return self.send(200, {"success": True, "contact": c})
                if method == "POST" and self.path.startswith("/crm/contacts/") and self.path.endswith(("/phones", "/emails")):
                    return self.send(200, {"success": True})
                if method == "POST" and self.path.startswith("/crm/statuses/") and self.path.endswith("/deals"):
                    d = dict(body, id=f"d{len(fake.deals) + 1}", statusId=self.path.split("/")[3])
                    fake.deals.append(d)
                    return self.send(200, {"success": True, "deal": d})
                return self.send(404, {"error": "no route"})

            def do_GET(self):
                self.handle_any("GET")

            def do_POST(self):
                self.handle_any("POST")

        class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True

        self.server = S(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


class BridgeTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeWeeek()
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.update({"WEEEK_TOKEN": "test-token", "WEEEK_STATUS_ID": "ST-NEW", "WEEEK_BASE": self.fake.url,
                           "QUEUE_DIR": str(Path(self.tmp.name) / "q"), "WEEEK_ASSIGNEES": "u-1", "LISTEN_PORT": "0"})
        self.cfg = wb.Config()
        self.queue = wb.Queue(self.cfg.queue)
        self.worker = wb.Worker(self.cfg, self.queue, wb.Weeek(self.cfg))

    def tearDown(self):
        self.fake.server.shutdown()
        self.fake.server.server_close()
        self.tmp.cleanup()

    def lead(self, **kw):
        base = {"name": "Иван Петров", "phone": "+7 (912) 345-67-89", "email": "", "company": "", "comment": COMMENT}
        base.update(kw)
        return base

    def run_one(self, raw):
        lead, why = wb.clean_lead(raw)
        self.assertIsNotNone(lead, why)
        lead_id = self.queue.put(lead)
        self.worker.process_all()
        return lead_id

    def test_new_contact_then_deal(self):
        self.run_one(self.lead())
        self.assertEqual(len(self.fake.deals), 1)
        deal = self.fake.deals[0]
        self.assertEqual(deal["statusId"], "ST-NEW")
        self.assertEqual(deal["title"], "Заявка с сайта: Иван Петров")
        self.assertEqual(deal["assignees"], ["u-1"])
        new = self.fake.contacts[-1]
        self.assertEqual(deal["contacts"], [new["id"]])
        self.assertEqual(new["firstName"], "Иван Петров")
        self.assertIn("Что интересно: РО-БОТ", deal["description"])
        self.assertIn("&lt;", wb.deal_description(self.lead(comment="<b>x</b>\n" + CONSENT), "id"))
        self.assertEqual(self.queue.size(), 0)
        # ключ уходит заголовком
        self.assertTrue(all(c[3] == "Bearer test-token" for c in self.fake.calls))

    def test_existing_contact_by_phone(self):
        self.run_one(self.lead(phone="8 917 000-00-00"))
        self.assertEqual(self.fake.deals[0]["contacts"], ["c-old"])
        self.assertFalse(any(c[1] == "/crm/contacts" and c[0] == "POST" for c in self.fake.calls))

    def test_fuzzy_search_not_trusted(self):
        # поиск отдаёт «Старого клиента» на любой запрос — номер другой, значит контакт новый
        self.run_one(self.lead(phone="+7 900 123-45-67"))
        self.assertNotEqual(self.fake.deals[0]["contacts"], ["c-old"])

    def test_existing_contact_by_email_case_insensitive(self):
        self.run_one(self.lead(phone="", email="boss@example.ru", company="ООО Ромашка"))
        deal = self.fake.deals[0]
        self.assertEqual(deal["contacts"], ["c-other"])
        self.assertEqual(deal["title"], "Заявка с сайта: ООО Ромашка — Иван Петров")

    def test_rejects_junk(self):
        for raw, why in [
            ([1, 2], "не объект JSON"),
            (self.lead(name=""), "нет имени"),
            (self.lead(phone="123", email=""), "нет телефона и почты"),
            (self.lead(comment="hello"), "нет отметки о согласии (не форма сайта)"),
            (self.lead(name="x" * 201), "поле name длиннее 200"),
            (self.lead(phone=5), "поле phone не строка"),
        ]:
            lead, reason = wb.clean_lead(raw)
            self.assertIsNone(lead)
            self.assertEqual(reason, why)
        lead, _ = wb.clean_lead(self.lead(email="not-an-email", company=None))
        self.assertEqual(lead["email"], "")
        self.assertEqual(lead["company"], "")

    def test_retry_then_success_without_duplicate_contact(self):
        self.fake.fail_next = 1  # первый запрос (поиск) падает
        lead_id = self.run_one(self.lead())
        self.assertEqual(self.queue.size(), 1)
        item = dict(self.queue.items())[lead_id]
        self.assertEqual(item["attempts"], 1)
        item["next_try"] = 0
        self.queue.write(lead_id, item)
        self.worker.process_all()
        self.assertEqual(len(self.fake.deals), 1)
        self.assertEqual(self.queue.size(), 0)

    def test_contact_kept_when_deal_fails(self):
        lead, _ = wb.clean_lead(self.lead())
        lead_id = self.queue.put(lead)
        orig = self.worker.api.create_deal
        self.worker.api.create_deal = lambda *a: (_ for _ in ()).throw(wb.WeeekError(503, "x", retry=True))
        self.worker.process_all()
        self.worker.api.create_deal = orig
        item = dict(self.queue.items())[lead_id]
        self.assertTrue(item["contact_id"])
        contacts_before = len(self.fake.contacts)
        item["next_try"] = 0
        self.queue.write(lead_id, item)
        self.worker.process_all()
        self.assertEqual(len(self.fake.contacts), contacts_before)  # второй раз контакт не создан
        self.assertEqual(len(self.fake.deals), 1)

    def test_client_error_goes_to_failed(self):
        self.fake.fail_next, self.fake.fail_code = 1, 400
        self.run_one(self.lead())
        self.assertEqual(self.queue.size(), 0)
        self.assertEqual(len(list(self.queue.failed.glob("*.json"))), 1)

    def test_give_up_after_deadline(self):
        lead, _ = wb.clean_lead(self.lead())
        lead_id = self.queue.put(lead)
        item = dict(self.queue.items())[lead_id]
        item["received"] = time.time() - self.cfg.give_up - 1
        self.queue.write(lead_id, item)
        self.fake.fail_next = 5
        self.worker.process_all()
        self.assertEqual(len(list(self.queue.failed.glob("*.json"))), 1)

    def test_http_endpoint(self):
        wb.Handler.cfg, wb.Handler.queue, wb.Handler.worker = self.cfg, self.queue, self.worker
        srv = wb.Server(("127.0.0.1", 0), wb.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"

        def post(body, path="/lead"):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
            req = urllib.request.Request(base + path, data=data, method="POST", headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())

        self.assertEqual(post(self.lead())[0], 202)
        self.assertEqual(post(self.lead(comment="spam"))[0], 422)
        self.assertEqual(post(b"{not json")[0], 400)
        self.assertEqual(post(b"x" * (wb.MAX_BODY + 1))[0], 413)
        self.assertEqual(post(self.lead(), "/other")[0], 404)
        with urllib.request.urlopen(base + "/health") as r:
            self.assertEqual(json.loads(r.read())["ok"], True)
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
