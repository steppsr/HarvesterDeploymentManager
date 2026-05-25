"""User-facing SSH error messages for GUI and CLI."""

from __future__ import annotations

from pathlib import Path

try:
    import asyncssh
except ImportError:
    asyncssh = None  # type: ignore


def explain_ssh_failure(
    exc: BaseException | str | None,
    *,
    host: str = "",
    key_path: str = "",
) -> tuple[str, bool]:
    """
    Return (message, offer_passphrase).

    offer_passphrase is True only when the private key is encrypted and
    a passphrase may unlock it — not for missing SSH setup on the host.
    """
    if exc is None:
        return ("SSH connection failed for an unknown reason.", False)

    if isinstance(exc, FileNotFoundError):
        return (
            f"SSH private key not found:\n{key_path or exc}\n\n"
            "Choose an existing key file (usually ~/.ssh/id_ed25519) or create one "
            "with ssh-keygen on this PC.",
            False,
        )

    if asyncssh is not None and isinstance(exc, asyncssh.KeyImportError):
        text = str(exc).lower()
        if "passphrase" in text or "encrypted" in text or "password" in text:
            return (
                "Your private key file is encrypted.\n\n"
                "Enter its passphrase to store it in the system keyring, "
                "or use an unencrypted key for automation.",
                True,
            )
        return (f"Could not read SSH private key:\n{exc}", False)

    text = str(exc).lower()
    host_line = f"Host: {host}\n\n" if host else ""

    if "getaddrinfo" in text or "name or service not known" in text or "11001" in text:
        return (
            f"{host_line}Cannot resolve this hostname.\n\n"
            "Check the host name or IP (e.g. 192.168.1.253) and that the machine "
            "is on your network.",
            False,
        )

    if "connection refused" in text:
        return (
            f"{host_line}Connection refused — nothing accepted SSH on port 22.\n\n"
            "On the Ubuntu host, install and start openssh-server, then add your "
            "public key to ~/.ssh/authorized_keys (see README — SSH setup).",
            False,
        )

    if "permission denied" in text or "authentication failed" in text:
        return (
            f"{host_line}Authentication failed — the server rejected this key.\n\n"
            "Install your public key (.pub) on the host for this user before "
            "testing. The app does not configure SSH for you; see README — SSH setup.",
            False,
        )

    if "timed out" in text or "timeout" in text:
        return (
            f"{host_line}Connection timed out.\n\n"
            "Check that the host is powered on, reachable on the LAN, and not "
            "blocking port 22.",
            False,
        )

    if "passphrase" in text or "encrypted key" in text or "key is encrypted" in text:
        return (
            "The private key appears to be encrypted.\n\n"
            "Enter its passphrase only if you use a password-protected key file.",
            True,
        )

    if key_path and not Path(key_path).expanduser().is_file():
        return (
            f"SSH private key not found: {key_path}\n\n"
            "Fix the key path or create a key with ssh-keygen.",
            False,
        )

    return (
        f"{host_line}SSH failed:\n{exc}\n\n"
        "If this is a new machine, complete SSH key setup on the host first "
        "(README — SSH setup), then try Test SSH again.",
        False,
    )
