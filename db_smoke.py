#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


REPO_ROOT = Path(__file__).resolve().parent
ENV_FILE = REPO_ROOT / ".env"
SESSION_KEY = "private:db-smoke"


def require_database_url() -> str:
    load_dotenv(ENV_FILE)
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("Missing DATABASE_URL in .env")
    return database_url


def main() -> None:
    database_url = require_database_url()

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT to_regclass('public.chat_sessions'),
                       to_regclass('public.chat_messages')
                """
            )
            sessions_table, messages_table = cur.fetchone()
            if sessions_table is None or messages_table is None:
                raise SystemExit("Required tables are missing. Start PostgreSQL with docker compose first.")

            cur.execute(
                """
                INSERT INTO chat_sessions (
                    session_key, session_type, source, user_wxid, title, last_message_at
                ) VALUES (%s, 'private', 'smoke', 'db-smoke', 'DB Smoke Session', NOW())
                ON CONFLICT (session_key) DO UPDATE
                SET title = EXCLUDED.title,
                    last_message_at = NOW()
                RETURNING id
                """,
                (SESSION_KEY,),
            )
            session_id = cur.fetchone()[0]

            cur.execute("DELETE FROM chat_messages WHERE session_id = %s", (session_id,))

            cur.executemany(
                """
                INSERT INTO chat_messages (
                    session_id, role, content, provider, model, prompt_tokens,
                    completion_tokens, total_tokens, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        session_id,
                        "user",
                        "hello from db smoke",
                        "smoke",
                        "manual",
                        4,
                        None,
                        4,
                        Jsonb({"source": "db_smoke"}),
                    ),
                    (
                        session_id,
                        "assistant",
                        "db smoke ok",
                        "smoke",
                        "manual",
                        None,
                        3,
                        7,
                        Jsonb({"source": "db_smoke"}),
                    ),
                ],
            )

            cur.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY id
                """,
                (session_id,),
            )
            rows = cur.fetchall()
            print("Smoke rows:", rows)

            if len(rows) != 2:
                raise SystemExit("Smoke test failed: expected 2 rows")

            cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
        conn.commit()

    print("Database smoke test passed")


if __name__ == "__main__":
    main()
