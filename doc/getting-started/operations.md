# Operations

Use the tray controller for everyday pause, resume, and log access. The scheduled-task supervisor is the normal production entry point; avoid running a separate daemon while it is active.

## Diagnostics

```powershell
# Show resolved account, local paths, credential availability, Ollama, Telegram, and browser checks
.\.venv\Scripts\python.exe -m xlistener check

# Inspect cursor, retention state, notifications, feedback, and learned tag affinity
.\.venv\Scripts\python.exe -m xlistener db-status

# Show configured game processes currently detected by Windows
.\.venv\Scripts\python.exe -m xlistener gaming-status
```

Useful one-off commands:

```powershell
.\.venv\Scripts\python.exe -m xlistener fetch-once --limit 5
.\.venv\Scripts\python.exe -m xlistener classify-latest
.\.venv\Scripts\python.exe -m xlistener notify-latest --dry-run
.\.venv\Scripts\python.exe -m xlistener run-once
```

`classify-latest` prints a model decision without delivering it. `notify-latest --dry-run` renders a qualifying notification without sending it. `run-once` executes one normal polling cycle, including baseline behavior and durable state updates.

## Background Service

The installation script registers two Windows scheduled tasks:

- **XListener Supervisor** starts the daemon, restarts it after unexpected exits, pauses it for configured games, and writes status.
- **XListener Tray** exposes local controls and opens logs.

The tray menu can pause or resume monitoring, start or stop the supervisor, and open the listener or supervisor log. Exiting the tray icon does not stop the supervisor.

For foreground diagnosis only:

```powershell
.\.venv\Scripts\python.exe -m xlistener run
```

To request a cooperative stop of a foreground or supervised daemon:

```powershell
.\.venv\Scripts\python.exe -m xlistener stop
```

## Logs and Runtime State

By default, inspect these local files:

```text
%LOCALAPPDATA%\XListener\xlistener.log
%LOCALAPPDATA%\XListener\supervisor.log
%LOCALAPPDATA%\XListener\supervisor-status.json
```

Logs rotate at roughly 5 MB with three retained backups. The status file reports the daemon PID, whether it is paused, and any detected game processes. See [Runtime and data](../engineering/runtime-and-data.md) for the full list of local files.

## Telegram Workflow

Each qualifying notification includes a 1–10 rating keyboard. Use it to record how useful the notification was:

- `1` means irrelevant or unwanted.
- `10` means very useful.

To recover a missed post, send a single `x.com/.../status/...` or `twitter.com/.../status/...` link to the configured private chat. XListener asks for a rating before it fetches or classifies the post. Pending requests expire after 24 hours.

## Recovery Guide

| Symptom | Recommended action |
|---|---|
| No posts are detected | Run `check`, then repeat `auth-x --manual` if the saved X session is unavailable. Review `xlistener.log`. |
| Telegram delivery fails | Confirm the bot token and private chat ID in `.env`; run `check` and review retry errors in the listener log. |
| Ollama is unavailable | Start Ollama and confirm `ollama list` includes the configured model. Failed work is retained for retry. |
| Monitoring is paused | Check the tray status, configured game executable names, and `%LOCALAPPDATA%\XListener\supervisor-status.json`. |
| Duplicate process warning | Use `scripts/status_xlistener_task.ps1`. Daemon and supervisor locks reject competing instances. |
| Old posts appeared or nothing appeared on first run | Review `fetcher.bootstrap_mode`; `baseline` is the recommended first-run setting. |
