"""SQLite fleet inventory (canonical store for the GUI)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from harvester_deploy.domain.models import ChiaNetwork, Harvester, NodeRole
from harvester_deploy.domain.network import parse_network
from harvester_deploy.persistence.config import AppConfig, DefaultsModel
from harvester_deploy.persistence.paths import default_db_path as _default_db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS defaults (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    ssh_port INTEGER NOT NULL,
    ssh_user TEXT NOT NULL,
    ssh_key_path TEXT NOT NULL,
    chia_root TEXT NOT NULL,
    chia_config_dir TEXT NOT NULL,
    activate_cmd TEXT NOT NULL,
    git_branch TEXT NOT NULL,
    upgrade_mode TEXT NOT NULL,
    enabled INTEGER NOT NULL,
    role TEXT NOT NULL,
    network TEXT NOT NULL DEFAULT 'mainnet'
);

CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    host TEXT NOT NULL,
    role TEXT NOT NULL,
    ssh_port INTEGER,
    ssh_user TEXT,
    ssh_key_path TEXT,
    chia_root TEXT,
    chia_config_dir TEXT,
    activate_cmd TEXT,
    git_branch TEXT,
    upgrade_mode TEXT,
    enabled INTEGER,
    last_known_version TEXT,
    farmer_host TEXT,
    network TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deploy_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_ts TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 0,
    json_path TEXT,
    total INTEGER NOT NULL,
    success_count INTEGER NOT NULL,
    failed_count INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS deploy_run_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    node_id TEXT NOT NULL,
    state TEXT NOT NULL,
    skipped_upgrade INTEGER NOT NULL DEFAULT 0,
    version_before TEXT,
    version_after TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT,
    steps_json TEXT,
    FOREIGN KEY (run_id) REFERENCES deploy_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_deploy_run_jobs_node
    ON deploy_run_jobs(node_id, run_id);
"""


def default_db_path() -> Path:
    return _default_db_path()


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r["name"] for r in rows}


def _migrate_schema(conn: sqlite3.Connection) -> None:
    defaults_cols = _table_columns(conn, "defaults")
    if "network" not in defaults_cols:
        conn.execute(
            "ALTER TABLE defaults ADD COLUMN network TEXT NOT NULL DEFAULT 'mainnet'"
        )

    node_cols = _table_columns(conn, "nodes")
    if "network" not in node_cols:
        conn.execute("ALTER TABLE nodes ADD COLUMN network TEXT")
        conn.execute(
            "UPDATE nodes SET network = 'mainnet' WHERE network IS NULL OR network = ''"
        )


def init_db(path: Path | None = None) -> Path:
    db_path = path or default_db_path()
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        _migrate_schema(conn)
        conn.commit()
    return db_path


def node_count(path: Path | None = None) -> int:
    db_path = path or default_db_path()
    if not db_path.is_file():
        return 0
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()
        return int(row["c"]) if row else 0


def _row_to_harvester(row: sqlite3.Row, defaults: DefaultsModel) -> Harvester:
    role = NodeRole(row["role"])
    network_raw = row["network"] if "network" in row.keys() else None
    if not network_raw:
        network_raw = defaults.network
    network = parse_network(network_raw)
    return Harvester(
        id=row["id"],
        display_name=row["display_name"],
        host=row["host"],
        role=role,
        network=network,
        ssh_port=row["ssh_port"] if row["ssh_port"] is not None else defaults.ssh_port,
        ssh_user=row["ssh_user"] or defaults.ssh_user,
        ssh_key_path=row["ssh_key_path"] or defaults.ssh_key_path,
        chia_root=row["chia_root"] or defaults.chia_root,
        chia_config_dir=row["chia_config_dir"] or defaults.chia_config_dir,
        activate_cmd=row["activate_cmd"] or defaults.activate_cmd,
        git_branch=row["git_branch"] or defaults.git_branch,
        upgrade_mode=row["upgrade_mode"] or defaults.upgrade_mode,
        enabled=bool(row["enabled"]) if row["enabled"] is not None else defaults.enabled,
        last_known_version=row["last_known_version"],
        farmer_host=row["farmer_host"],
    )


def load_config_from_db(path: Path | None = None) -> AppConfig:
    db_path = path or default_db_path()
    init_db(db_path)
    with _connect(db_path) as conn:
        drow = conn.execute("SELECT * FROM defaults WHERE id = 1").fetchone()
        if drow is None:
            defaults = DefaultsModel()
        else:
            defaults = DefaultsModel(
                ssh_port=drow["ssh_port"],
                ssh_user=drow["ssh_user"],
                ssh_key_path=drow["ssh_key_path"],
                chia_root=drow["chia_root"],
                chia_config_dir=drow["chia_config_dir"],
                activate_cmd=drow["activate_cmd"],
                git_branch=drow["git_branch"],
                upgrade_mode=drow["upgrade_mode"],
                enabled=bool(drow["enabled"]),
                role=drow["role"],
                network=drow["network"] if "network" in drow.keys() else "mainnet",
            )
        rows = conn.execute(
            "SELECT * FROM nodes ORDER BY sort_order, id"
        ).fetchall()
    harvesters = [_row_to_harvester(r, defaults) for r in rows]
    return AppConfig(defaults=defaults, harvesters=harvesters)


def save_config_to_db(config: AppConfig, path: Path | None = None) -> Path:
    db_path = path or default_db_path()
    init_db(db_path)
    d = config.defaults
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM defaults")
        conn.execute("DELETE FROM nodes")
        conn.execute(
            """
            INSERT INTO defaults (
                id, ssh_port, ssh_user, ssh_key_path, chia_root, chia_config_dir,
                activate_cmd, git_branch, upgrade_mode, enabled, role, network
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                d.ssh_port,
                d.ssh_user,
                d.ssh_key_path,
                d.chia_root,
                d.chia_config_dir,
                d.activate_cmd,
                d.git_branch,
                d.upgrade_mode,
                1 if d.enabled else 0,
                d.role,
                d.network,
            ),
        )
        for order, h in enumerate(config.harvesters):
            conn.execute(
                """
                INSERT INTO nodes (
                    id, display_name, host, role, ssh_port, ssh_user, ssh_key_path,
                    chia_root, chia_config_dir, activate_cmd, git_branch, upgrade_mode,
                    enabled, last_known_version, farmer_host, network, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    h.id,
                    h.display_name,
                    h.host,
                    h.role.value,
                    h.ssh_port,
                    h.ssh_user,
                    h.ssh_key_path,
                    h.chia_root,
                    h.chia_config_dir,
                    h.activate_cmd,
                    h.git_branch,
                    h.upgrade_mode,
                    1 if h.enabled else 0,
                    h.last_known_version,
                    h.farmer_host,
                    h.network.value,
                    order,
                ),
            )
        conn.commit()
    return db_path
