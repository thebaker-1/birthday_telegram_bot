import json
import os
import sqlite3

import psycopg
from psycopg import OperationalError


class BotStore:
    def reconnect(self):
        if self.use_postgres:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = psycopg.connect(self.database_url or "")
            self.cursor = self.conn.cursor()

    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.chat_ids_file = os.path.join(base_dir, "chat_ids.json")
        self.require_database = os.getenv("REQUIRE_DATABASE", "").strip().lower() in {"1", "true", "yes", "on"}
        self.database_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
        if self.require_database and not self.database_url:
            raise RuntimeError("Database is required, but DATABASE_URL is not set.")
        self.use_postgres = bool(self.database_url)
        if self.use_postgres:
            self.conn = psycopg.connect(self.database_url or "")
            self.cursor = self.conn.cursor()
            self._init_postgres_tables()
            self.active_chat_ids = self._load_active_chats_from_db()
            print("[store] Using Postgres backend.")
        else:
            self.conn = sqlite3.connect(os.path.join(base_dir, "birthdays.db"), check_same_thread=False)
            self.cursor = self.conn.cursor()
            self._init_sqlite_tables()
            self.active_chat_ids = self._load_chat_ids()
            print("[store] Using local SQLite/JSON fallback backend.")

    def _init_sqlite_tables(self):
        self.cursor.execute("PRAGMA table_info(birthdays)")
        existing_columns = {row[1] for row in self.cursor.fetchall()}
        if "chat_id" not in existing_columns:
            if existing_columns:
                self.cursor.execute("ALTER TABLE birthdays RENAME TO birthdays_legacy")
            self.cursor.execute(
                "CREATE TABLE birthdays (chat_id INTEGER, user_id INTEGER, username TEXT, birthday TEXT, display_name TEXT)"
            )
            if existing_columns:
                self.cursor.execute(
                    "INSERT INTO birthdays (chat_id, user_id, username, birthday, display_name) "
                    "SELECT 0, user_id, username, birthday, COALESCE(display_name, username) FROM birthdays_legacy"
                )
                self.cursor.execute("DROP TABLE birthdays_legacy")
        elif "display_name" not in existing_columns:
            self.cursor.execute("ALTER TABLE birthdays ADD COLUMN display_name TEXT")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_birthdays_chat_id ON birthdays(chat_id)")
        self.conn.commit()

    def _init_postgres_tables(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS birthdays (
                id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                chat_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL DEFAULT 0,
                username TEXT NOT NULL DEFAULT '',
                birthday DATE NOT NULL,
                display_name TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS active_chats (
                chat_id BIGINT PRIMARY KEY,
                source TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_birthdays_chat_id ON birthdays(chat_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_birthdays_chat_birthday ON birthdays(chat_id, birthday)")
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_birthdays_chat_user_id ON birthdays(chat_id, user_id) WHERE user_id <> 0"
        )
        self.cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_birthdays_chat_username ON birthdays(chat_id, lower(username)) WHERE user_id = 0 AND username <> ''"
        )
        self.conn.commit()

    def _load_active_chats_from_db(self):
        self.cursor.execute("SELECT chat_id FROM active_chats")
        return {row[0] for row in self.cursor.fetchall()}

    def _load_chat_ids(self):
        if os.path.exists(self.chat_ids_file):
            try:
                with open(self.chat_ids_file, "r") as file_handle:
                    return set(json.load(file_handle))
            except Exception as error:
                print(f"Failed to load chat IDs: {error}")
        return set()

    def save_chat_ids(self):
        if self.use_postgres:
            return
        try:
            with open(self.chat_ids_file, "w") as file_handle:
                json.dump(list(self.active_chat_ids), file_handle)
        except Exception as error:
            print(f"Failed to save chat IDs: {error}")

    def track_chat_id(self, chat_id, source):
        if chat_id is None:
            return
        if chat_id not in self.active_chat_ids:
            self.active_chat_ids.add(chat_id)
            if self.use_postgres:
                self.cursor.execute(
                    "INSERT INTO active_chats (chat_id, source) VALUES (%s, %s) ON CONFLICT (chat_id) DO NOTHING",
                    (chat_id, source),
                )
                self.conn.commit()
            else:
                self.save_chat_ids()
        print(f"Tracked chat ({source}): {chat_id}")

    def save_birthday(self, chat_id, user_id, username, birthday, display_name):
        for attempt in range(2):
            try:
                if self.use_postgres and user_id:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
                elif self.use_postgres:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=%s AND username=%s", (chat_id, username))
                elif user_id:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=? AND user_id=?", (chat_id, user_id))
                else:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=? AND username=?", (chat_id, username))
                if self.use_postgres:
                    self.cursor.execute(
                        "INSERT INTO birthdays (chat_id, user_id, username, birthday, display_name) VALUES (%s, %s, %s, %s, %s)",
                        (chat_id, user_id, username, birthday, display_name),
                    )
                else:
                    self.cursor.execute(
                        "INSERT INTO birthdays (chat_id, user_id, username, birthday, display_name) VALUES (?, ?, ?, ?, ?)",
                        (chat_id, user_id, username, birthday, display_name),
                    )
                self.conn.commit()
                break
            except OperationalError:
                if attempt == 1:
                    raise
                self.reconnect()
            except Exception:
                raise

    def get_all_birthdays(self, chat_id):
        for attempt in range(2):
            try:
                if self.use_postgres:
                    self.cursor.execute(
                        "SELECT username, TO_CHAR(birthday, 'YYYY-MM-DD'), display_name FROM birthdays WHERE chat_id=%s",
                        (chat_id,),
                    )
                else:
                    self.cursor.execute("SELECT username, birthday, display_name FROM birthdays WHERE chat_id=?", (chat_id,))
                result = self.cursor.fetchall()
                return result if result is not None else []
            except OperationalError:
                if attempt == 1:
                    break
                self.reconnect()
            except Exception:
                break
        return []

    def get_birthday_for_user(self, chat_id, user_id):
        for attempt in range(2):
            try:
                if self.use_postgres:
                    self.cursor.execute(
                        "SELECT TO_CHAR(birthday, 'YYYY-MM-DD') FROM birthdays WHERE chat_id=%s AND user_id=%s",
                        (chat_id, user_id),
                    )
                else:
                    self.cursor.execute("SELECT birthday FROM birthdays WHERE chat_id=? AND user_id=?", (chat_id, user_id))
                return self.cursor.fetchone()
            except OperationalError:
                if attempt == 1:
                    raise
                self.reconnect()
            except Exception:
                raise

    def delete_birthday_for_user(self, chat_id, user_id):
        for attempt in range(2):
            try:
                if self.use_postgres:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=%s AND user_id=%s", (chat_id, user_id))
                else:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=? AND user_id=?", (chat_id, user_id))
                self.conn.commit()
                return self.cursor.rowcount > 0
            except OperationalError:
                if attempt == 1:
                    raise
                self.reconnect()
            except Exception:
                raise

    def delete_birthday_for_username(self, chat_id, username):
        for attempt in range(2):
            try:
                if self.use_postgres:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=%s AND username=%s", (chat_id, username))
                else:
                    self.cursor.execute("DELETE FROM birthdays WHERE chat_id=? AND username=?", (chat_id, username))
                self.conn.commit()
                return self.cursor.rowcount > 0
            except OperationalError:
                if attempt == 1:
                    raise
                self.reconnect()
            except Exception:
                raise

    def import_legacy_birthdays(self, chat_id):
        if self.use_postgres:
            return 0
        self.cursor.execute("SELECT user_id, username, birthday, display_name FROM birthdays WHERE chat_id=0")
        copied = 0
        for user_id, username, birthday, display_name in self.cursor.fetchall():
            if user_id:
                self.cursor.execute("SELECT 1 FROM birthdays WHERE chat_id=? AND user_id=?", (chat_id, user_id))
            else:
                self.cursor.execute("SELECT 1 FROM birthdays WHERE chat_id=? AND username=?", (chat_id, username))
            if self.cursor.fetchone():
                continue
            self.cursor.execute(
                "INSERT INTO birthdays (chat_id, user_id, username, birthday, display_name) VALUES (?, ?, ?, ?, ?)",
                (chat_id, user_id, username, birthday, display_name),
            )
            copied += 1
        self.conn.commit()
        return copied