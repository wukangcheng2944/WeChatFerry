# WeChatFerry Python Client

This folder contains the local Python client and bot entry points for the Windows WeChat workflow.

## Requirements

- Windows
- Compatible Windows WeChat: `3.9.12.51`
- Python `>=3.8`
- Built native files copied into `clients/python/wcferry`
- PostgreSQL reachable through `DATABASE_URL`
- An OpenAI-compatible API endpoint reachable through `OPENAI_BASE_URL`

## Native Build

Build the native layer first from the repository root:

```bat
cd WeChatFerry
build_vs2022.cmd Release
```

## Environment

Copy `.env.example` to `.env` in the repository root and configure:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`
- `OPENAI_SYSTEM_PROMPT`
- `OPENAI_TIMEOUT`
- `OPENAI_MAX_HISTORY`

For the same ephone-compatible endpoint already used in other local projects, set:

- `OPENAI_BASE_URL=https://api.ephone.chat/v1`
- `OPENAI_MODEL=gemini-3.1-pro-preview`

## Install

The recommended path is the root start script:

```bat
start_bot.bat wechat
```

For database-only verification without WeChat:

```bat
start_bot.bat db
```

If you want to run manually:

```bat
cd clients\python
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r ..\..\requirements.txt
python openai_bot.py
```

## Runtime Behavior

`Wcf()` without a `host` argument runs in local mode. In that mode the client:

- loads `SDK.dll`
- opens WeChat if needed
- injects `spy.dll`
- starts a local RPC service on port `10086`
- waits for login by default

The OpenAI bot then:

- processes all private text messages
- processes group text messages only when the bot is mentioned
- upserts a row in `chat_sessions`
- loads recent AI conversation history from `chat_messages`
- calls the configured OpenAI-compatible `chat.completions` endpoint
- writes successful turns back to `chat_messages`

## Files

- `test.py`: upstream demo
- `bot_demo.py`: simple rule-based demo
- `openai_bot.py`: OpenAI-compatible PostgreSQL-backed bot
- `wcferry/client.py`: main WeChat client implementation

`chat_messages.metadata` is now a structured JSON document with `session`, `wechat`, `llm`, `message`, and `extra` sections.
