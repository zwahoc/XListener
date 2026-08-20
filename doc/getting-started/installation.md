# Installation

This guide installs XListener for a Windows user session. It is written for the project's supported target: **Windows 11**. macOS and Linux are not supported deployment targets and have not been tested.

## Before You Begin

Install the following:

- Python 3.11–3.14
- Git
- Google Chrome
- [Ollama for Windows](https://ollama.com/download/windows)
- A Telegram bot and the ID of the private chat that should receive notifications
- An X account for XListener's dedicated authenticated browser profile

Use a dedicated X account and browser profile. Do not point XListener at the Chrome profile you use every day.

## Install the Application

Clone the repository and create a virtual environment:

```powershell
git clone https://github.com/zwahoc/XListener.git
Set-Location XListener
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

Pull the text model configured by default:

```powershell
ollama pull qwen3:8b
```

The optional `media` dependency group is reserved for planned media work. Installing it does not enable image or video understanding in the current release.

```powershell
python -m pip install -e ".[dev,media]"
```

## Create Local Configuration

Copy the tracked templates. These local files contain personal configuration and must not be committed.

```powershell
Copy-Item .env.example .env
Copy-Item config/config.example.yaml config.yaml
Copy-Item config/preferences.example.yaml preferences.yaml
```

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`. Set `X_MONITORED_HANDLE` there if you want it to override the YAML account setting. See [Configuration](configuration.md) for all available settings.

## Authenticate X

Store the X username and password in Windows Credential Manager, then open the dedicated browser profile for a manual sign-in:

```powershell
.\.venv\Scripts\python.exe scripts/store_x_credentials.py
.\.venv\Scripts\python.exe -m xlistener auth-x --manual
```

Complete any normal X sign-in steps in the browser and close the browser window when finished. XListener reuses the saved session for later fetches. It does not solve CAPTCHAs or automated challenges.

Verify the installation before enabling background operation:

```powershell
.\.venv\Scripts\python.exe -m xlistener check
```

## Register Background Startup

Register the windowless supervisor and tray controller to start at user logon:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_xlistener_task.ps1
powershell -ExecutionPolicy Bypass -File scripts/status_xlistener_task.ps1
```

The installer creates `XListener Supervisor` and `XListener Tray` scheduled tasks. Both use `pythonw.exe`, so no console window remains open after sign-in.

To remove both tasks later:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/remove_xlistener_task.ps1
```

Continue with [Operations](operations.md) for normal controls, diagnostics, and recovery.
