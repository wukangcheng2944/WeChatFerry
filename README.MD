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

### 2. Create a local config

Copy `.env.example` to `.env` in the repository root and fill in:

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

### 3. Start the bot

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

The Python bot automatically creates a minimal table named `ai_chat_messages` on startup if it does not exist.

Stored records include:

- `session_id`
- `chat_type`
- `chat_key`
- `role`
- `content`
- `wx_sender`
- `wx_roomid`
- `created_at`

Only successful AI turns are stored: one `user` message and one `assistant` message per turn.

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
