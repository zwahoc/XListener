"""Store X credentials in the user's OS credential vault."""

from getpass import getpass

import keyring


SERVICE = "XListener"


def main() -> None:
    print(f"Credential backend: {type(keyring.get_keyring()).__name__}")
    username = input("X username (without @): ").strip()
    if not username:
        raise SystemExit("Username cannot be empty.")

    password = getpass("X password: ")
    if not password:
        raise SystemExit("Password cannot be empty.")

    keyring.set_password(SERVICE, "x_username", username)
    keyring.set_password(SERVICE, "x_password", password)
    print("Saved X username and password to the XListener credential service.")


if __name__ == "__main__":
    main()

