# WeChatFerry Python Client

This folder contains the local Python client for the Windows WeChat bot workflow.

## Requirements

- Windows
- Compatible Windows WeChat: `3.9.12.51`
- Python `>=3.8`
- Built native files copied into `clients/python/wcferry`

Build the native layer first from the repository root:

```bat
cd WeChatFerry
build_vs2022.cmd Release
```

## Install

```bat
cd clients\python
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -e .
```

## Run

Minimal test:

```bat
python test.py
```

Simple bot example:

```bat
python bot_demo.py
```

## Local Mode

`Wcf()` without a `host` argument runs in local mode. In that mode the client:

- loads `sdk.dll`
- opens WeChat if needed
- injects `spy.dll`
- starts a local RPC service on port `10086`
- waits for login by default

## Common Pattern

```python
from wcferry import Wcf

wcf = Wcf(debug=True)
wcf.enable_receiving_msg()

while True:
    msg = wcf.get_msg()
    print(msg)
```

## Files

- `test.py`: upstream demo
- `bot_demo.py`: simple command-style bot example
- `wcferry/client.py`: main client implementation
