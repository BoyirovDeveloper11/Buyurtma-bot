#!/usr/bin/env python3
"""Lead bot for Boyirov: sayt, Telegram bot, mobil ilova."""

from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "leads.sqlite"
API = "https://api.telegram.org/bot{token}/{method}"
OWNER_USERNAME = "boyirov_dev"
PUBLIC_CONTACT = "@Boyirov_dev"

SERVICES = {
    "site": "Sayt",
    "bot": "Telegram bot",
    "app": "Mobil ilova",
    "unsure": "Aniq bilmayman",
}
SITE_TYPES = {
    "landing": "Bir sahifa",
    "company": "Kompaniya sayti",
    "shop": "Do'kon",
    "other": "Boshqa",
}

BTN_START = "🚀 Start"
BTN_HELP = "ℹ️ Yordam"
MIN_BUSINESS_LEN = 5
MIN_NOTE_LEN = 5

WELCOME = (
    "Assalomu alaykum. Men Boyirovman.\n"
    "Sayt, Telegram bot va mobil ilova yasayman.\n\n"
    "Qaysi biri kerak?"
)
ASK_SITE = "Qanday sayt kerak?"
ASK_OTHER = "Qanday sayt kerakligini bir gapda yozing (kamida 5 ta harf)."
ASK_BUSINESS = (
    "Biznesingiz nomi nima?\n"
    "Masalan: o'quv markaz, klinika, kafe.\n"
    f"(Kamida {MIN_BUSINESS_LEN} ta harf yozing.)"
)
DONE = (
    "Arizangiz yuborildi.\n\n"
    f"Batafsil gaplashish uchun menga yozing: {PUBLIC_CONTACT}\n"
    "Men ham shu yerdan javob beraman."
)
HELP_TEXT = (
    "Bot qoidalari:\n\n"
    "1. Pastdagi 🚀 Start tugmasini bosing.\n"
    "2. Xizmatni tanlang: Sayt, Telegram bot yoki Mobil ilova.\n"
    "3. Agar sayt tanlasangiz — turini tanlang.\n"
    "4. Biznes nomini yozing (kamida 5 ta harf).\n"
    "5. Ariza menga keladi, sizga esa mening usernameim chiqadi.\n\n"
    f"Bog'lanish: {PUBLIC_CONTACT}\n\n"
    "Boshlash uchun 🚀 Start ni bosing."
)
NEED_START = (
    "Botdan foydalanish uchun pastdagi 🚀 Start tugmasini bosing.\n"
    "Yordam kerak bo'lsa ℹ️ Yordam ni bosing."
)
NEED_BUTTON = "Iltimos, ekrandagi tugmalardan birini tanlang."
NEED_BUSINESS_LEN = (
    f"Biznes nomi juda qisqa.\n"
    f"Kamida {MIN_BUSINESS_LEN} ta harf yozing.\n"
    "Masalan: o'quv markaz yoki stomatologiya."
)
NEED_NOTE_LEN = (
    f"Juda qisqa yozdingiz.\n"
    f"Kamida {MIN_NOTE_LEN} ta harf bilan qanday sayt kerakligini yozing."
)


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS owners (
            chat_id INTEGER PRIMARY KEY,
            username TEXT,
            added_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            full_name TEXT,
            username TEXT,
            service TEXT NOT NULL,
            site_type TEXT,
            note TEXT,
            business TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            user_id INTEGER PRIMARY KEY,
            step TEXT NOT NULL,
            service TEXT,
            site_type TEXT,
            note TEXT,
            prompt_id INTEGER
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "prompt_id" not in columns:
        conn.execute("ALTER TABLE sessions ADD COLUMN prompt_id INTEGER")
    conn.commit()
    return conn


def kb(rows: list[list[tuple[str, str]]]) -> dict:
    return {
        "inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row]
            for row in rows
        ]
    }


def main_keyboard() -> dict:
    return {
        "keyboard": [[{"text": BTN_START}, {"text": BTN_HELP}]],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def service_keyboard() -> dict:
    return kb(
        [
            [("Sayt", "svc:site"), ("Telegram bot", "svc:bot")],
            [("Mobil ilova", "svc:app")],
            [("Aniq bilmayman", "svc:unsure")],
        ]
    )


def site_keyboard() -> dict:
    return kb(
        [
            [("Bir sahifa", "type:landing"), ("Kompaniya sayti", "type:company")],
            [("Do'kon", "type:shop"), ("Boshqa", "type:other")],
        ]
    )


def lead_text(lead: dict) -> str:
    username = f"@{lead['username']}" if lead.get("username") else "username yo'q"
    lines = [
        "Yangi ariza",
        f"Ism: {lead.get('full_name') or '—'}",
        f"Username: {username}",
        f"Xizmat: {SERVICES.get(lead['service'], lead['service'])}",
    ]
    if lead.get("site_type"):
        lines.append(f"Tur: {SITE_TYPES.get(lead['site_type'], lead['site_type'])}")
    if lead.get("note"):
        lines.append(f"Izoh: {lead['note']}")
    lines.append(f"Biznes: {lead['business']}")
    return "\n".join(lines)


def customer_name(user: dict | None) -> str:
    if not user:
        return ""
    parts = [user.get("first_name") or "", user.get("last_name") or ""]
    return " ".join(p for p in parts if p).strip()


def is_start_command(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("/start") or text.strip() == BTN_START


def is_help_command(text: str) -> bool:
    t = text.strip().lower()
    return t.startswith("/help") or t.startswith("/yordam") or text.strip() == BTN_HELP


class Store:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def save_session(self, user_id: int, step: str, service=None, site_type=None, note=None) -> None:
        self.conn.execute(
            """
            INSERT INTO sessions (user_id, step, service, site_type, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                step=excluded.step,
                service=excluded.service,
                site_type=excluded.site_type,
                note=excluded.note
            """,
            (user_id, step, service, site_type, note),
        )
        self.conn.commit()

    def set_prompt(self, user_id: int, message_id: int) -> None:
        self.conn.execute(
            "UPDATE sessions SET prompt_id = ? WHERE user_id = ?",
            (message_id, user_id),
        )
        self.conn.commit()

    def session(self, user_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM sessions WHERE user_id = ?", (user_id,)
        ).fetchone()

    def clear_session(self, user_id: int) -> None:
        self.conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def add_owner(self, chat_id: int, username: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO owners (chat_id, username, added_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET username=excluded.username
            """,
            (chat_id, username, int(time.time())),
        )
        self.conn.commit()

    def owner_ids(self) -> list[int]:
        env_owner = os.environ.get("OWNER_CHAT_ID", "").strip()
        ids = [int(env_owner)] if env_owner.isdigit() else []
        rows = self.conn.execute("SELECT chat_id FROM owners").fetchall()
        for row in rows:
            if row["chat_id"] not in ids:
                ids.append(row["chat_id"])
        return ids

    def add_lead(self, lead: dict) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO leads (
                user_id, full_name, username, service, site_type, note, business, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead["user_id"],
                lead.get("full_name"),
                lead.get("username"),
                lead["service"],
                lead.get("site_type"),
                lead.get("note"),
                lead["business"],
                int(time.time()),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def recent(self, limit: int = 10) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM leads ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        )


class Bot:
    def __init__(self, token: str, store: Store) -> None:
        self.token = token
        self.store = store
        self.offset = 0

    def call(self, method: str, payload: dict) -> dict:
        req = urllib.request.Request(
            API.format(token=self.token, method=method),
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=70) as res:
                body = json.loads(res.read().decode())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")
            raise RuntimeError(f"{method} failed: {exc.code} {detail}") from exc
        if not body.get("ok"):
            raise RuntimeError(f"{method} failed: {body}")
        return body

    def send(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        with_main_keyboard: bool = False,
    ) -> int:
        payload: dict = {"chat_id": chat_id, "text": text}
        if with_main_keyboard and reply_markup is None:
            payload["reply_markup"] = main_keyboard()
        elif reply_markup is not None:
            payload["reply_markup"] = reply_markup
        body = self.call("sendMessage", payload)
        return int(body["result"]["message_id"])

    def delete(self, chat_id: int, message_id: int | None) -> None:
        if not message_id:
            return
        try:
            self.call("deleteMessage", {"chat_id": chat_id, "message_id": int(message_id)})
        except RuntimeError:
            try:
                self.call(
                    "editMessageReplyMarkup",
                    {
                        "chat_id": chat_id,
                        "message_id": int(message_id),
                        "reply_markup": {"inline_keyboard": []},
                    },
                )
            except RuntimeError:
                return

    def ask(
        self,
        chat_id: int,
        user_id: int,
        text: str,
        reply_markup: dict | None = None,
    ) -> None:
        message_id = self.send(chat_id, text, reply_markup)
        self.store.set_prompt(user_id, message_id)

    def acknowledge(self, callback_id: str, text: str | None = None) -> None:
        payload: dict = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        self.call("answerCallbackQuery", payload)

    def remember_owner(self, user: dict, chat_id: int) -> None:
        username = (user.get("username") or "").lower()
        if username == OWNER_USERNAME:
            self.store.add_owner(chat_id, username)

    def notify_owners(self, lead: dict, customer_id: int) -> None:
        link = f"tg://user?id={customer_id}"
        text = f"{lead_text(lead)}\nProfil: {link}"
        owners = self.store.owner_ids()
        if not owners:
            return
        for owner_id in owners:
            if owner_id == customer_id:
                continue
            self.send(owner_id, text, with_main_keyboard=True)

    def finish(self, chat_id: int, user: dict, session: sqlite3.Row, business: str) -> None:
        lead = {
            "user_id": user["id"],
            "full_name": customer_name(user),
            "username": user.get("username"),
            "service": session["service"],
            "site_type": session["site_type"],
            "note": session["note"],
            "business": business.strip(),
        }
        self.store.add_lead(lead)
        self.store.clear_session(user["id"])
        self.notify_owners(lead, user["id"])
        self.send(chat_id, DONE, with_main_keyboard=True)

    def on_start(self, chat_id: int, user: dict) -> None:
        self.remember_owner(user, chat_id)
        self.store.save_session(user["id"], "service")
        extra = ""
        if (user.get("username") or "").lower() == OWNER_USERNAME:
            extra = "\n\nBu akkaunt egasi sifatida saqlandi. Yangi arizalar shu yerga keladi."
        # Avval pastki Start/Yordam klaviaturasini o'rnatamiz
        self.send(chat_id, "Quyidagi xizmatlardan birini tanlang.", with_main_keyboard=True)
        self.ask(chat_id, user["id"], WELCOME + extra, service_keyboard())

    def on_help(self, chat_id: int) -> None:
        self.send(chat_id, HELP_TEXT, with_main_keyboard=True)

    def on_callback(self, callback: dict) -> None:
        data = callback.get("data") or ""
        user = callback["from"]
        message = callback["message"]
        chat_id = message["chat"]["id"]
        message_id = message["message_id"]
        self.remember_owner(user, chat_id)
        if data.startswith("open:"):
            self.acknowledge(callback["id"])
            return
        session = self.store.session(user["id"])
        step = session["step"] if session else ""
        expected = (
            "service"
            if data.startswith("svc:")
            else "site_type"
            if data.startswith("type:")
            else ""
        )
        if expected and step != expected:
            self.acknowledge(callback["id"], "Bu savol yopilgan")
            self.delete(chat_id, message_id)
            return
        self.acknowledge(callback["id"])
        self.delete(chat_id, message_id)
        if data.startswith("svc:"):
            service = data.split(":", 1)[1]
            if service not in SERVICES:
                return
            if service == "site":
                self.store.save_session(user["id"], "site_type", service=service)
                self.ask(chat_id, user["id"], ASK_SITE, site_keyboard())
            else:
                self.store.save_session(user["id"], "business", service=service)
                self.ask(chat_id, user["id"], ASK_BUSINESS)
            return
        if data.startswith("type:"):
            site_type = data.split(":", 1)[1]
            if site_type not in SITE_TYPES:
                return
            service = session["service"] if session else "site"
            if site_type == "other":
                self.store.save_session(user["id"], "note", service=service, site_type=site_type)
                self.ask(chat_id, user["id"], ASK_OTHER)
            else:
                self.store.save_session(
                    user["id"], "business", service=service, site_type=site_type
                )
                self.ask(chat_id, user["id"], ASK_BUSINESS)

    def on_text(self, message: dict) -> None:
        chat_id = message["chat"]["id"]
        user = message["from"]
        text = (message.get("text") or "").strip()
        self.remember_owner(user, chat_id)

        if is_help_command(text):
            self.on_help(chat_id)
            return

        if is_start_command(text):
            previous = self.store.session(user["id"])
            if previous and previous["prompt_id"]:
                self.delete(chat_id, previous["prompt_id"])
            self.on_start(chat_id, user)
            return

        if text.startswith("/leads"):
            if chat_id not in self.store.owner_ids():
                self.send(chat_id, "Bu buyruq faqat egaga.", with_main_keyboard=True)
                return
            rows = self.store.recent()
            if not rows:
                self.send(chat_id, "Hali ariza yo'q.", with_main_keyboard=True)
                return
            chunks = [lead_text(dict(row)) for row in rows]
            self.send(chat_id, "\n\n".join(chunks)[:4000], with_main_keyboard=True)
            return

        session = self.store.session(user["id"])

        # Hali Start bosilmagan
        if session is None:
            self.send(chat_id, NEED_START, with_main_keyboard=True)
            return

        # Xizmat tanlash bosqichi — faqat tugma, oddiy matn emas
        if session["step"] == "service":
            self.send(chat_id, NEED_BUTTON, with_main_keyboard=True)
            return

        # Sayt turi tanlash bosqichi
        if session["step"] == "site_type":
            self.send(chat_id, NEED_BUTTON, with_main_keyboard=True)
            return

        if session["step"] == "note":
            if len(text) < MIN_NOTE_LEN:
                self.send(chat_id, NEED_NOTE_LEN, with_main_keyboard=True)
                return
            self.delete(chat_id, session["prompt_id"])
            self.delete(chat_id, message["message_id"])
            self.store.save_session(
                user["id"],
                "business",
                service=session["service"],
                site_type=session["site_type"],
                note=text[:300],
            )
            self.ask(chat_id, user["id"], ASK_BUSINESS)
            return

        if session["step"] == "business":
            if len(text) < MIN_BUSINESS_LEN:
                self.send(chat_id, NEED_BUSINESS_LEN, with_main_keyboard=True)
                return
            self.delete(chat_id, session["prompt_id"])
            self.delete(chat_id, message["message_id"])
            self.finish(chat_id, user, session, text[:200])
            return

        # Noma'lum holat — qayta start
        self.send(chat_id, NEED_START, with_main_keyboard=True)

    def handle(self, update: dict) -> None:
        if "message" in update:
            message = update["message"]
            if message.get("text"):
                self.on_text(message)
            elif message.get("from"):
                self.send(
                    message["chat"]["id"],
                    NEED_START,
                    with_main_keyboard=True,
                )
        elif "callback_query" in update:
            self.on_callback(update["callback_query"])

    def run(self) -> None:
        self.call("deleteWebhook", {})
        while True:
            body = self.call(
                "getUpdates",
                {
                    "offset": self.offset,
                    "timeout": 50,
                    "allowed_updates": ["message", "callback_query"],
                },
            )
            for update in body.get("result", []):
                self.offset = update["update_id"] + 1
                try:
                    self.handle(update)
                except Exception as exc:
                    print(f"update error: {exc}", flush=True)


def self_test() -> None:
    db = ROOT / "self-test.sqlite"
    if db.exists():
        db.unlink()
    global DB_PATH
    DB_PATH = db
    store = Store(connect())
    user = {"id": 7, "first_name": "Aziz", "username": "aziz_cafe"}
    store.save_session(7, "business", service="site", site_type="landing")
    session = store.session(7)
    assert session is not None
    lead = {
        "user_id": 7,
        "full_name": customer_name(user),
        "username": "aziz_cafe",
        "service": "site",
        "site_type": "landing",
        "note": None,
        "business": "kafe",
    }
    assert "Sayt" in lead_text(lead)
    assert "@aziz_cafe" in lead_text(lead)
    store.add_lead(lead)
    assert store.recent(1)[0]["business"] == "kafe"
    store.add_owner(99, OWNER_USERNAME)
    assert store.owner_ids() == [99]
    assert is_start_command("🚀 Start")
    assert is_help_command("ℹ️ Yordam")
    db.unlink()
    print("self-test ok")


def start_health_server() -> None:
    """Railway healthcheck uchun PORT da oddiy HTTP server."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    port = int(os.environ.get("PORT", "0") or "0")
    if port <= 0:
        return

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, format, *args):  # noqa: A003
            return

    server = HTTPServer(("0.0.0.0", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Health server: http://0.0.0.0:{port}/", flush=True)


if __name__ == "__main__":
    import sys

    if "--self-test" in sys.argv:
        self_test()
        raise SystemExit(0)
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN yo'q. Railway Variables ga qo'ying.")
    start_health_server()
    print("Bot ishga tushdi (polling).", flush=True)
    Bot(token, Store(connect())).run()
