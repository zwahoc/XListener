# Installation

## Supported Environment

The supported and tested deployment is Windows 11 on the development laptop. The core Python modules are ordinary cross-platform code, but the authenticated Chrome workflow, Credential Manager integration, game supervisor, system tray, and startup scripts are Windows-oriented and have not been validated as a complete macOS or Linux deployment.

## Prerequisites

- Python 3.11 through 3.14
- Git
- Google Chrome
- Ollama for Windows
- A Telegram bot and private chat
- An X account dedicated to this automation

## Setup

~~~powershell
git clone https://github.com/zwahoc/XListener.git
Set-Location XListener
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m playwright install chromium
~~~

The text milestone does not require media dependencies. For the planned image/video work, the optional package set can be installed without changing the current pipeline:

~~~powershell
python -m pip install -e ".[dev,media]"
~~~

Video processing will also require an FFmpeg installation when that roadmap milestone begins.

Pull the configured text model in Ollama:

~~~powershell
ollama pull qwen3:8b
~~~

Copy the local configuration templates:

~~~powershell
Copy-Item .env.example .env
Copy-Item config/config.example.yaml config.yaml
Copy-Item config/preferences.example.yaml preferences.yaml
~~~

Fill in .env, then follow [Configuration](configuration.md). Do not commit .env, config.yaml, preferences.yaml, browser state, or runtime files.

## X Authentication

Store the X credentials in Windows Credential Manager:

~~~powershell
.\.venv\Scripts\python.exe scripts/store_x_credentials.py
.\.venv\Scripts\python.exe -m xlistener auth-x --manual
~~~

Complete login in the dedicated Chrome profile. Close that browser window when finished so XListener can capture and verify the session. Later fetches reuse the saved profile and only attempt controlled reauthentication when the session is unavailable.

## Startup Installation

Register the windowless supervisor and tray controller:

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts/install_xlistener_task.ps1
powershell -ExecutionPolicy Bypass -File scripts/status_xlistener_task.ps1
~~~

The tasks run at interactive user logon through pythonw.exe. Remove them with scripts/remove_xlistener_task.ps1.
