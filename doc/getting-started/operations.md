# Operations

## Diagnostics

~~~powershell
.\.venv\Scripts\python.exe -m xlistener check
.\.venv\Scripts\python.exe -m xlistener db-status
.\.venv\Scripts\python.exe -m xlistener gaming-status
~~~

Useful one-shot commands:

~~~powershell
.\.venv\Scripts\python.exe -m xlistener fetch-once --limit 5
.\.venv\Scripts\python.exe -m xlistener classify-latest
.\.venv\Scripts\python.exe -m xlistener notify-latest --dry-run
.\.venv\Scripts\python.exe -m xlistener run-once
~~~

classify-latest prints the model result and timing without sending or retaining ignored content. run-once performs one complete polling cycle.

## Background Operation

The normal deployment is the Task Scheduler supervisor plus tray controller. The daemon itself is a child process and should not be launched separately while the supervisor is active.

The tray menu can pause monitoring while keeping the application installed, resume it after a cooldown, stop the supervisor, and open both logs. Closing the tray icon does not stop background monitoring.

For a direct foreground diagnostic run:

~~~powershell
.\.venv\Scripts\python.exe -m xlistener run
~~~

Stop a foreground or supervised daemon cooperatively with:

~~~powershell
.\.venv\Scripts\python.exe -m xlistener stop
~~~

## Logs and State

Inspect:

~~~text
%LOCALAPPDATA%\XListener\xlistener.log
%LOCALAPPDATA%\XListener\supervisor.log
%LOCALAPPDATA%\XListener\supervisor-status.json
~~~

The logs are rotating and sanitized. The status file reports whether the daemon is running, paused, or stopped and lists detected game processes.

## Telegram Workflow

Notifications include a summary, model reasoning, importance, generated tags, Malaysia-time timestamps, and a View tweet link. Use the inline 1-10 rating buttons whenever a notification is useful or irrelevant. To recover a missed post, send one X status URL by itself; the bot asks for a rating before performing the expensive fetch and classification operation.

## Common Recovery

- No X posts: check the saved Chrome session with auth-x --manual and inspect xlistener.log.
- No Telegram messages: run check, verify the bot token/chat ID, and inspect retry errors.
- Model unavailable: start Ollama and verify ollama list contains qwen3:4b.
- Monitoring paused: check the tray status, configured game processes, and pause.request.
- Duplicate startup concern: use status_xlistener_task.ps1; the daemon and supervisor locks reject competing instances.
