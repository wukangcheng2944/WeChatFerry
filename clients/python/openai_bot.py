#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from queue import Empty
from threading import Thread
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from psycopg.types.json import Jsonb

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


def normalize_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    return base_url


def infer_provider_name(base_url: str) -> str:
    parsed = urlparse(base_url)
    hostname = parsed.hostname or base_url
    return hostname.removeprefix("api.")


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
        openai_base_url = normalize_base_url(os.getenv("OPENAI_BASE_URL", ""))
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


@dataclass
class SessionRoute:
    session_key: str
    session_type: str
    chat_key: str
    receiver: str
    prompt: str
    user_wxid: Optional[str]
    room_wxid: Optional[str]
    title: str


@dataclass
class CompletionResult:
    content: str
    provider: str
    model: str
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    finish_reason: Optional[str]
    metadata: Dict[str, Any]


def build_message_metadata(
    route: SessionRoute,
    role: str,
    provider: str,
    model: str,
    *,
    finish_reason: Optional[str] = None,
    usage: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Jsonb:
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "source": "wechat",
        "transport": "wcf",
        "message": {
            "role": role,
        },
        "session": {
            "key": route.session_key,
            "type": route.session_type,
            "chat_key": route.chat_key,
            "title": route.title,
        },
        "wechat": {
            "receiver": route.receiver,
            "user_wxid": route.user_wxid,
            "room_wxid": route.room_wxid,
        },
        "llm": {
            "provider": provider,
            "model": model,
        },
    }
    if finish_reason:
        payload["llm"]["finish_reason"] = finish_reason
    if usage:
        payload["llm"]["usage"] = usage
    if extra:
        payload["extra"] = extra
    return Jsonb(payload)


class PgConversationStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.ensure_schema()

    def ensure_schema(self) -> None:
        ddl = """
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TABLE IF NOT EXISTS chat_sessions (
            id BIGSERIAL PRIMARY KEY,
            session_key TEXT NOT NULL UNIQUE,
            session_type TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'wechat',
            user_wxid TEXT,
            room_wxid TEXT,
            title TEXT,
            last_message_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chat_sessions_session_type_check
                CHECK (session_type IN ('private', 'group')),
            CONSTRAINT chat_sessions_participant_check
                CHECK (
                    (session_type = 'private' AND user_wxid IS NOT NULL AND room_wxid IS NULL)
                    OR
                    (session_type = 'group' AND room_wxid IS NOT NULL)
                )
        );

        CREATE TABLE IF NOT EXISTS chat_messages (
            id BIGSERIAL PRIMARY KEY,
            session_id BIGINT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'ephone',
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chat_messages_role_check
                CHECK (role IN ('system', 'user', 'assistant'))
        );

        CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created_at
            ON chat_messages (session_id, created_at DESC, id DESC);

        CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_message_at
            ON chat_sessions (last_message_at DESC NULLS LAST);

        DROP TRIGGER IF EXISTS trg_chat_sessions_updated_at ON chat_sessions;

        CREATE TRIGGER trg_chat_sessions_updated_at
        BEFORE UPDATE ON chat_sessions
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def upsert_session(self, route: SessionRoute) -> int:
        sql = """
        INSERT INTO chat_sessions (
            session_key, session_type, source, user_wxid, room_wxid, title
        ) VALUES (%s, %s, 'wechat', %s, %s, %s)
        ON CONFLICT (session_key) DO UPDATE
        SET
            title = COALESCE(EXCLUDED.title, chat_sessions.title),
            user_wxid = COALESCE(EXCLUDED.user_wxid, chat_sessions.user_wxid),
            room_wxid = COALESCE(EXCLUDED.room_wxid, chat_sessions.room_wxid)
        RETURNING id
        """
        params = (
            route.session_key,
            route.session_type,
            route.user_wxid,
            route.room_wxid,
            route.title,
        )
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                session_id = cur.fetchone()[0]
            conn.commit()
        return int(session_id)

    def load_recent_messages(self, session_id: int, limit: int) -> List[Dict[str, str]]:
        sql = """
        SELECT role, content
        FROM chat_messages
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

    def append_turn(self, session_id: int, route: SessionRoute, result: CompletionResult) -> None:
        user_usage: Dict[str, Any] = {}
        if result.prompt_tokens is not None:
            user_usage["prompt_tokens"] = result.prompt_tokens
        user_metadata = build_message_metadata(
            route,
            "user",
            result.provider,
            result.model,
            usage=user_usage or None,
            extra={"direction": "inbound"},
        )
        assistant_metadata = build_message_metadata(
            route,
            "assistant",
            result.provider,
            result.model,
            finish_reason=result.finish_reason,
            usage=result.metadata or None,
            extra={"direction": "outbound"},
        )

        insert_sql = """
        INSERT INTO chat_messages (
            session_id, role, content, provider, model,
            prompt_tokens, completion_tokens, total_tokens, metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        update_session_sql = """
        UPDATE chat_sessions
        SET last_message_at = NOW()
        WHERE id = %s
        """
        rows = [
            (
                session_id,
                "user",
                route.prompt,
                result.provider,
                result.model,
                result.prompt_tokens,
                None,
                result.prompt_tokens,
                user_metadata,
            ),
            (
                session_id,
                "assistant",
                result.content,
                result.provider,
                result.model,
                None,
                result.completion_tokens,
                result.total_tokens,
                assistant_metadata,
            ),
        ]
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.executemany(insert_sql, rows)
                cur.execute(update_session_sql, (session_id,))
            conn.commit()


class OpenAIResponder:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._provider = infer_provider_name(config.openai_base_url)
        self._client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            timeout=config.openai_timeout,
        )

    def reply(self, history: List[Dict[str, str]], user_message: str) -> CompletionResult:
        messages: List[Dict[str, str]] = []
        if self._config.openai_system_prompt:
            messages.append({"role": "system", "content": self._config.openai_system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = self._client.chat.completions.create(
            model=self._config.openai_model,
            messages=messages,
        )
        choice = response.choices[0]
        content = self._normalize_content(choice.message.content or "")
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

        usage_metadata: Dict[str, Any] = {}
        if prompt_tokens is not None:
            usage_metadata["prompt_tokens"] = prompt_tokens
        if completion_tokens is not None:
            usage_metadata["completion_tokens"] = completion_tokens
        if total_tokens is not None:
            usage_metadata["total_tokens"] = total_tokens

        return CompletionResult(
            content=content,
            provider=self._provider,
            model=getattr(response, "model", self._config.openai_model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            finish_reason=getattr(choice, "finish_reason", None),
            metadata=usage_metadata,
        )

    @staticmethod
    def _normalize_content(content: Any) -> str:
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
            session_id = self._store.upsert_session(route)
            history = self._store.load_recent_messages(session_id, self._config.openai_max_history)
        except Exception as exc:
            LOG.exception("Failed to load conversation history: %s", exc)
            self._wcf.send_text("Conversation storage is unavailable. Please try again later.", route.receiver)
            return

        try:
            result = self._responder.reply(history, route.prompt)
        except Exception as exc:
            LOG.exception("OpenAI request failed: %s", exc)
            self._wcf.send_text("AI service is temporarily unavailable. Please try again later.", route.receiver)
            return

        if not result.content:
            LOG.warning("OpenAI returned an empty reply")
            self._wcf.send_text("AI returned an empty reply. Please try again.", route.receiver)
            return

        try:
            self._store.append_turn(session_id, route, result)
        except Exception as exc:
            LOG.exception("Failed to persist conversation history: %s", exc)

        self._wcf.send_text(result.content, route.receiver)
        LOG.info("Replied in %s", route.session_key)

    def _build_route(self, msg) -> Optional[SessionRoute]:
        prompt = (msg.content or "").strip()
        if not prompt:
            return None

        if msg.from_group():
            if not msg.is_at(self._self_wxid):
                return None
            prompt = self._strip_group_mention(prompt)
            if not prompt:
                return None
            return SessionRoute(
                session_key=f"group:{msg.roomid}",
                session_type="group",
                chat_key=msg.roomid,
                receiver=msg.roomid,
                prompt=prompt,
                user_wxid=None,
                room_wxid=msg.roomid,
                title=msg.roomid,
            )

        return SessionRoute(
            session_key=f"private:{msg.sender}",
            session_type="private",
            chat_key=msg.sender,
            receiver=msg.sender,
            prompt=prompt,
            user_wxid=msg.sender,
            room_wxid=None,
            title=msg.sender,
        )

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
