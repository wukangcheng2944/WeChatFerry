# WeChatFerry

Independent WeChatFerry fork with a verified VS2022 build path.

This fork is based on the last usable source snapshot before the upstream `master` branch was cleared. It keeps the original project structure, adds a working VS2022 build flow, and is suitable for local Windows WeChat bot development.

## Status

- Supported Windows WeChat version: `3.9.12.51`
- Verified toolchain: Visual Studio 2022
- Verified outputs: `sdk.dll`, `spy.dll`
- Verified local Python client flow: `clients/python`

The WeChat version check is enforced in [spy.h](./WeChatFerry/spy/spy.h) and [spy.cpp](./WeChatFerry/spy/spy.cpp).

## Quick Start

### 1. Build native binaries

```bat
cd WeChatFerry
build_vs2022.cmd Release
```

After a successful build, the key files are copied to:

- `WeChatFerry\Out`
- `clients\python\wcferry`

### 2. Create a Python environment

```bat
cd ..\clients\python
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -e .
```

### 3. Run the demo bot

```bat
python bot_demo.py
```

### 4. Open and log in to WeChat

When `Wcf()` starts in local mode, it loads `sdk.dll`, starts the local RPC service, opens WeChat if needed, injects `spy.dll`, and waits for login.

If you see a version mismatch dialog, your installed Windows WeChat is not `3.9.12.51`.

## How To Use It As A WeChat Bot

The simplest path is the Python client in `clients/python`.

The demo bot included in this fork does the following:

- connects to local WeChat via `Wcf()`
- enables message receiving
- replies `pong` when a private chat or group message body equals `ping`
- replies `status: ok` when the body equals `status`

You can extend the message handler to:

- route by sender `wxid`
- route by group `roomid`
- call external HTTP APIs
- store state in SQLite or Redis
- implement command-style bots

## Usage Notes

- This project targets Windows desktop WeChat, not the official public platform API.
- The local client machine must have a compatible WeChat installed.
- First run may show the disclaimer confirmation dialog.
- If you build `Debug`, use `build_vs2022.cmd Debug`.
- Direct solution build also works after the VS2022 fixes:

```bat
cd WeChatFerry
msbuild WeChatFerry.sln /p:Configuration=Release /p:Platform=x64
```

## Python Entry Points

- Minimal example: [clients/python/test.py](./clients/python/test.py)
- Bot example added in this fork: [clients/python/bot_demo.py](./clients/python/bot_demo.py)
- Main client wrapper: [clients/python/wcferry/client.py](./clients/python/wcferry/client.py)

## Repository

- Fork repository: <https://github.com/wukangcheng2944/WeChatFerry>
- Upstream source project: <https://github.com/lich0821/WeChatFerry>

## Disclaimer

Read the project disclaimer before use:

- [WeChatFerry/DISCLAIMER.md](./WeChatFerry/DISCLAIMER.md)
