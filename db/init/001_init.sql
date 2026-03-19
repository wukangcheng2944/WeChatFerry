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
