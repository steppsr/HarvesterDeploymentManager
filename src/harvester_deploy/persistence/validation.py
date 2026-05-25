"""Inventory validation for GUI and persistence."""

from __future__ import annotations

import re

from harvester_deploy.domain.models import ChiaNetwork, Harvester, NodeRole

_ID_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


def validate_node(
    harvester: Harvester,
    existing: list[Harvester],
    *,
    original_id: str | None = None,
) -> list[str]:
    """Return human-readable validation errors (empty if valid)."""
    errors: list[str] = []
    node_id = harvester.id.strip()

    if not node_id:
        errors.append("ID is required.")
    elif not _ID_RE.match(node_id):
        errors.append(
            "ID must start with a letter and use only lowercase letters, "
            "digits, hyphens, and underscores."
        )

    if not harvester.host.strip():
        errors.append("Host is required.")

    if not harvester.display_name.strip():
        errors.append("Display name is required.")

    if not harvester.ssh_user.strip():
        errors.append("SSH user is required.")

    if not harvester.ssh_key_path.strip():
        errors.append("SSH key path is required.")

    if not harvester.chia_root.strip():
        errors.append("Chia root path is required.")

    if not harvester.chia_config_dir.strip():
        errors.append("Chia config directory is required.")

    if harvester.role == NodeRole.FARMER and harvester.farmer_host:
        errors.append("Farmer host is only valid on harvester-role nodes.")

    if harvester.network not in (ChiaNetwork.MAINNET, ChiaNetwork.TESTNET):
        errors.append("Network must be mainnet or testnet.")

    for other in existing:
        if other.id == node_id and other.id != (original_id or ""):
            errors.append(f"Duplicate id '{node_id}'.")
            break

    return errors
