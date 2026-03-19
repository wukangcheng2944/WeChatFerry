#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from threading import Thread
from typing import Dict, List, Optional

import psycopg
from dotenv import load_dotenv
from openai import OpenAI

from wcferry import Wcf


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("OpenAIBot")

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / ".env"
DEFAULT_SYSTEM_PROMPT = (
    "You are a concise and helpful assistant replying inside WeChat. "
    "Reply in Chinese unless the user explicitly asks for another language."
)
DEFAULT_TIMEOUT = 60.0
DEFAULT_HISTORY_SIZE = 12


@dataclass
class AppConfig:
    database_url: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    openai_system_prompt: str
    openai_timeout: float
    openai_max_history: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        load_dotenv(ENV_FILE)

        database_url = os.getenv("DATABASE_URL", "").strip()
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        openai_base_url = os.getenv("OPENAI_BASE_URL", "").strip()
        openai_model = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
        openai_system_prompt = os.getenv("OPENAI_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT).strip() or DEFAULT_SYSTEM_PROMPT
        openai_timeout = float(os.getenv("OPENAI_TIMEOUT", DEFAULT_TIMEOUT))
        openai_max_history = int(os.getenv("OPENAI_MAX_HISTORY", DEFAULT_HISTORY_SIZE))

        missing = [
            name
            for name, value in (
                ("DATABASE_URL", database_url),
                ("OPENAI_API_KEY", openai_api_key),
                ("OPENAI_BASE_URL", openai_base_url),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        if openai_max_history < 1:
            raise ValueError("OPENAI_MAX_HISTORY must be >= 1")

        return cls(
            database_url=database_url,
            openai_api_key=openai_api_key,
            openai_base_url=openai_base_url,
            openai_model=openai_model,
            openai_system_prompt=openai_system_prompt,
            openai_timeout=openai_timeout,
            openai_max_history=openai_max_history,
        )


class PgConversationStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.ensure_schema()

    def ensure_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS ai_chat_messages (
            id BIGSERIAL PRIMARY KEY,
            session_id TEXT NOT NULL,
            chat_type TEXT NOT NULL,
            chat_key TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            wx_sender TEXT,
            wx_roomid TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_session_created_at
            ON ai_chat_messages (session_id, created_at DESC, id DESC);
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def load_recent_messages(self, session_id: str, limit: int) -> List[Dict[str, str]]:
        sql = """
        SELECT role, content
        FROM ai_chat_messages
        WHERE session_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT %s
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (session_id, limit))
                rows = cur.fetchall()

        rows.reverse()
        return [{"role": role, "content": content} for role, content in rows]

    def append_turn(
        self,
        session_id: str,
        chat_type: str,
        chat_key: str,
        user_content: str,
        assistant_content: str,
        wx_sender: str,
        wx_roomid: str,
    ) -> None:
        sql = """
        INSERT INTO ai_chat_messages (
            session_id, chat_type, chat_key, role, content, wx_sender, wx_roomid
        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (session_id, chat_type, chat_key, "user", user_content, wx_sender, wx_roomid),
            (session_id, chat_type, chat_key, "assistant", assistant_content, wx_sender, wx_roomid),
        ]
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(sql, params)
            conn.commit()


class OpenAIResponder:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            timeout=config.openai_timeout,
        )

    def reply(self, history: List[Dict[str, str]], user_message: str) -> str:
        messages: List[Dict[str, str]] = []
        if self._config.openai_system_prompt:
            messages.append({"role": "system", "content": self._config.openai_system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self._client.chat.completions.create(
            model=self._config.openai_model,
            messages=messages,
        )
        content = response.choices[0].message.content or ""
        return self._normalize_content(content)

    @staticmethod
    def _normalize_content(content) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for item in content:
                text_value = getattr(item, "text", None)
                if text_value:
                    parts.append(text_value)
                elif isinstance(item, dict) and item.get("text"):
                    parts.append(item["text"])
            return "\n".join(parts).strip()

        return str(content).strip()


class WeChatOpenAIBot:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._store = PgConversationStore(config.database_url)
        self._responder = OpenAIResponder(config)
        self._wcf = Wcf(debug=True)
        self._self_wxid = self._wcf.get_self_wxid()

    def start(self) -> None:
        LOG.info("Logged in: %s", self._wcf.is_login())
        LOG.info("Self wxid: %s", self._self_wxid)
        if not self._wcf.enable_receiving_msg(pyq=False):
            raise RuntimeError("Failed to enable WeChat message receiving")

        Thread(target=self._message_loop, name="OpenAIBotLoop", daemon=True).start()
        LOG.info("Bot is running")
        self._wcf.keep_running()

    def _message_loop(self) -> None:
        while self._wcf.is_receiving_msg():
            try:
                msg = self._wcf.get_msg()
            except Empty:
                continue
            except Exception as exc:
                LOG.exception("Message receive error: %s", exc)
                continue

            try:
                self._handle_message(msg)
            except Exception as exc:
                LOG.exception("Message handling error: %s", exc)

    def _handle_message(self, msg) -> None:
        if msg.from_self() or not msg.is_text():
            return

        route = self._build_route(msg)
        if route is None:
            return

        try:
            history = self._store.load_recent_messages(route["session_id"], self._config.openai_max_history)
        except Exception as exc:
            LOG.exception("Failed to load conversation history: %s", exc)
            self._wcf.send_text("Conversation storage is unavailable. Please try again later.", route["receiver"])
            return

        try:
            reply_text = self._responder.reply(history, route["prompt"])
        except Exception as exc:
            LOG.exception("OpenAI request failed: %s", exc)
            self._wcf.send_text("AI service is temporarily unavailable. Please try again later.", route["receiver"])
            return

        if not reply_text:
            LOG.warning("OpenAI returned an empty reply")
            self._wcf.send_text("AI returned an empty reply. Please try again.", route["receiver"])
            return

        try:
            self._store.append_turn(
                session_id=route["session_id"],
                chat_type=route["chat_type"],
                chat_key=route["chat_key"],
                user_content=route["prompt"],
                assistant_content=reply_text,
                wx_sender=msg.sender,
                wx_roomid=msg.roomid or "",
            )
        except Exception as exc:
            LOG.exception("Failed to persist conversation history: %s", exc)

        self._wcf.send_text(reply_text, route["receiver"])
        LOG.info("Replied in %s", route["session_id"])

    def _build_route(self, msg) -> Optional[Dict[str, str]]:
        prompt = (msg.content or "").strip()
        if not prompt:
            return None

        if msg.from_group():
            if not msg.is_at(self._self_wxid):
                return None
            prompt = self._strip_group_mention(prompt)
            if not prompt:
                return None
            return {
                "session_id": f"group:{msg.roomid}",
                "chat_type": "group",
                "chat_key": msg.roomid,
                "receiver": msg.roomid,
                "prompt": prompt,
            }

        return {
            "session_id": f"private:{msg.sender}",
            "chat_type": "private",
            "chat_key": msg.sender,
            "receiver": msg.sender,
            "prompt": prompt,
        }

    @staticmethod
    def _strip_group_mention(text: str) -> str:
        cleaned = text.replace("\u2005", " ")
        cleaned = re.sub(r"^(?:@\S+\s*)+", "", cleaned).strip()
        return cleaned


def main() -> None:
    try:
        config = AppConfig.from_env()
    except Exception as exc:
        LOG.error("Configuration error: %s", exc)
        raise SystemExit(1) from exc

    try:
        bot = WeChatOpenAIBot(config)
        bot.start()
    except Exception as exc:
        LOG.exception("Bot startup failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
