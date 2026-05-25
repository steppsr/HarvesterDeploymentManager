"""Optional SSH key passphrase storage via system keyring."""

from __future__ import annotations

SERVICE_NAME = "harvester-deploy"


def keyring_available() -> bool:
    try:
        import keyring  # noqa: F401

        return True
    except Exception:
        return False


def get_passphrase(key_path: str) -> str | None:
    if not keyring_available():
        return None
    import keyring

    return keyring.get_password(SERVICE_NAME, key_path)


def set_passphrase(key_path: str, passphrase: str) -> bool:
    if not keyring_available():
        return False
    import keyring

    keyring.set_password(SERVICE_NAME, key_path, passphrase)
    return True


def delete_passphrase(key_path: str) -> None:
    if not keyring_available():
        return
    import keyring

    try:
        keyring.delete_password(SERVICE_NAME, key_path)
    except Exception:
        pass
