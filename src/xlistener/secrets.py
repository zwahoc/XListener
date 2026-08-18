"""Credential-vault access for X authentication."""

from __future__ import annotations

from getpass import getpass

import keyring


SERVICE_NAME = "XListener"
USERNAME_KEY = "x_username"
PASSWORD_KEY = "x_password"


def get_x_credentials() -> tuple[str, str] | None:
    username = keyring.get_password(SERVICE_NAME, USERNAME_KEY)
    password = keyring.get_password(SERVICE_NAME, PASSWORD_KEY)
    if not username or not password:
        return None
    return username, password


def ensure_x_credentials() -> tuple[str, str]:
    existing = get_x_credentials()
    if existing:
        return existing

    username = input("X username (without @): ").strip().lstrip("@").lower()
    if not username:
        raise ValueError("X username cannot be empty")
    password = getpass("X password: ")
    if not password:
        raise ValueError("X password cannot be empty")

    keyring.set_password(SERVICE_NAME, USERNAME_KEY, username)
    keyring.set_password(SERVICE_NAME, PASSWORD_KEY, password)
    return username, password

