# WeChatFerry

Independent WeChatFerry fork with a verified VS2022 build path and an OpenAI-compatible WeChat bot example backed by PostgreSQL.

This fork is based on the last usable source snapshot before the upstream `master` branch was cleared. It keeps the original project structure, fixes the VS2022 build flow, and adds a production-oriented Python bot entry point.

## Status

- Supported Windows WeChat version: `3.9.12.51`
- Verified native build toolchain: Visual Studio 2022
- Verified native outputs: `SDK.dll`, `spy.dll`
- Local repo path: `D:\workspace\WeChatFerry`
- Python bot entry point: `clients/python/openai_bot.py`

The runtime version check is enforced in `WeChatFerry/spy/spy.h` and `WeChatFerry/spy/spy.cpp`.

## Quick Start

### 1. Build native binaries

```bat
cd WeChatFerry
build_vs2022.cmd Release
```

After a successful build, the native files are copied to:

- `WeChatFerry\Out`
- `clients\python\wcferry`

### 2. Start local PostgreSQL

```bat
docker compose up -d postgres
```

This repository now includes a dedicated local PostgreSQL service on host port `5437`. The initial schema is created from `db/init/001_init.sql` and contains `chat_sessions` and `chat_messages`.

Useful database commands:

```bat
db_up.bat
db_reset.bat
python db_smoke.py
```

### 3. Create a local config

Copy `.env.example` to `.env` in the repository root and fill in:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

For the existing ephone-compatible setup used in other local projects, the working values are:

- `OPENAI_BASE_URL=https://api.ephone.chat/v1`
- `OPENAI_MODEL=gemini-3.1-pro-preview`

### 4. Start the bot

```bat
start_bot.bat
```

The start script creates a virtual environment, installs dependencies from `requirements.txt`, validates that `.env` exists, checks `SDK.dll` and `spy.dll`, and then starts the Python bot.

## Bot Behavior

- Private chat: every text message is sent to the AI service
- Group chat: only messages that `@` the bot are sent to the AI service
- Only AI conversations are stored in PostgreSQL
- Conversation history is keyed by:
  - private chat: `sender`
  - group chat: `roomid`
- Model protocol: OpenAI-compatible `chat.completions`
- Default model: `gpt-5-mini`

## PostgreSQL Storage

The repository now includes a dedicated local schema bootstrap for PostgreSQL:

- `chat_sessions`
- `chat_messages`

The intended session keying is:

- private chat: `private:{sender}`
- group chat: `group:{roomid}`

This round prepares storage and environment only. The WeChat client integration path is intentionally left unchanged for now.

The OpenAI-compatible bot code now reads and writes against these two tables instead of the earlier single-table prototype.

## Python Entry Points

- Minimal upstream example: `clients/python/test.py`
- Local simple demo: `clients/python/bot_demo.py`
- OpenAI-compatible bot: `clients/python/openai_bot.py`
- Main client wrapper: `clients/python/wcferry/client.py`

## Usage Notes

- This project targets Windows desktop WeChat, not the official public platform API.
- The local machine must have a compatible WeChat installed.
- First run may show the disclaimer confirmation dialog.
- If your installed WeChat version is not `3.9.12.51`, startup will fail with a version mismatch dialog.
- If native files are missing, run `WeChatFerry\build_vs2022.cmd Release` first.

## Repository

- Fork repository: <https://github.com/wukangcheng2944/WeChatFerry>
- Upstream source project: <https://github.com/lich0821/WeChatFerry>

## Disclaimer

Read the project disclaimer before use:

- `WeChatFerry/DISCLAIMER.md`
