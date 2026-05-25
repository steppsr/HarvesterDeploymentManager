"""Add or edit a single fleet node."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harvester_deploy.domain.models import ChiaNetwork, Harvester, NodeRole
from harvester_deploy.domain.network import DEFAULT_CHIA_CONFIG_DIR
from harvester_deploy.gui.async_runner import AsyncTaskBridge
from harvester_deploy.gui.services import node_test_ssh
from harvester_deploy.persistence.keyring_support import (
    keyring_available,
    set_passphrase,
)
from harvester_deploy.persistence.validation import validate_node
from harvester_deploy.ssh.client import expand_key_path
from harvester_deploy.ssh.errors import explain_ssh_failure


class NodeEditorDialog(QDialog):
    def __init__(
        self,
        harvester: Harvester | None,
        existing: list[Harvester],
        *,
        defaults_display: str = "",
        parent: QWidget | None = None,
        async_thread=None,
    ) -> None:
        super().__init__(parent)
        self._existing = existing
        self._original_id = harvester.id if harvester else None
        self._async_thread = async_thread
        self.result_harvester: Harvester | None = None

        is_edit = harvester is not None
        self.setWindowTitle("Edit node" if is_edit else "Add node")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        if defaults_display:
            hint = QLabel(f"Defaults: {defaults_display}")
            hint.setStyleSheet("color: #6c757d; font-size: 11px;")
            hint.setWordWrap(True)
            layout.addWidget(hint)

        form = QFormLayout()
        self._id = QLineEdit()
        self._id.setPlaceholderText("e.g. tarkin")
        if is_edit:
            self._id.setText(harvester.id)
            self._id.setReadOnly(True)
        form.addRow("ID:", self._id)

        self._display_name = QLineEdit()
        form.addRow("Display name:", self._display_name)

        self._host = QLineEdit()
        self._host.setPlaceholderText("hostname or IP")
        form.addRow("Host:", self._host)

        self._role = QComboBox()
        self._role.addItem("Harvester", NodeRole.HARVESTER.value)
        self._role.addItem("Farmer", NodeRole.FARMER.value)
        self._role.currentIndexChanged.connect(self._on_role_changed)
        form.addRow("Role:", self._role)

        self._network = QComboBox()
        self._network.addItem("Mainnet", ChiaNetwork.MAINNET.value)
        self._network.addItem("Testnet", ChiaNetwork.TESTNET.value)
        form.addRow("Network:", self._network)
        network_hint = QLabel(
            "For filtering and badges only — does not change the config directory."
        )
        network_hint.setStyleSheet("color: #6c757d; font-size: 11px;")
        network_hint.setWordWrap(True)
        form.addRow("", network_hint)

        self._farmer_host = QLineEdit()
        self._farmer_host.setPlaceholderText("farmer hostname (harvesters)")
        form.addRow("Farmer host:", self._farmer_host)

        self._ssh_user = QLineEdit()
        form.addRow("SSH user:", self._ssh_user)

        key_row = QHBoxLayout()
        self._ssh_key = QLineEdit()
        key_row.addWidget(self._ssh_key)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_key)
        key_row.addWidget(browse)
        form.addRow("SSH key:", key_row)

        self._chia_root = QLineEdit()
        form.addRow("Chia root:", self._chia_root)

        self._chia_config = QLineEdit()
        form.addRow("Config dir:", self._chia_config)

        self._version = QLineEdit()
        self._version.setPlaceholderText("optional")
        form.addRow("Last version:", self._version)

        self._enabled = QCheckBox("Node enabled for deploy/status")
        self._enabled.setChecked(True)
        form.addRow("", self._enabled)

        layout.addLayout(form)

        if harvester:
            self._fill(harvester)
        else:
            self._apply_defaults_from_peer()

        self._on_role_changed()

        ssh_hint = QLabel(
            "Test SSH only verifies that this PC can log in to the host. "
            "It does not configure SSH on a new machine — install your public key "
            "on the host first (README → SSH setup)."
        )
        ssh_hint.setWordWrap(True)
        ssh_hint.setStyleSheet("color: #6c757d; font-size: 11px;")
        layout.addWidget(ssh_hint)

        buttons = QDialogButtonBox()
        self._btn_test = buttons.addButton("Test SSH", QDialogButtonBox.ButtonRole.ActionRole)
        self._btn_test.clicked.connect(self._test_ssh)
        buttons.addButton(QDialogButtonBox.StandardButton.Save)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_defaults_from_peer(self) -> None:
        if not self._existing:
            self._ssh_user.setText("steve")
            self._ssh_key.setText("~/.ssh/id_ed25519")
            self._chia_root.setText("~/chia-blockchain")
            self._chia_config.setText(DEFAULT_CHIA_CONFIG_DIR)
            idx = self._network.findData(ChiaNetwork.MAINNET.value)
            if idx >= 0:
                self._network.setCurrentIndex(idx)
            return
        sample = self._existing[0]
        self._ssh_user.setText(sample.ssh_user)
        self._ssh_key.setText(sample.ssh_key_path)
        self._chia_root.setText(sample.chia_root)
        self._chia_config.setText(sample.chia_config_dir)

    def _fill(self, h: Harvester) -> None:
        self._display_name.setText(h.display_name)
        self._host.setText(h.host)
        idx = self._role.findData(h.role.value, Qt.ItemDataRole.UserRole)
        if idx >= 0:
            self._role.setCurrentIndex(idx)
        nidx = self._network.findData(h.network.value, Qt.ItemDataRole.UserRole)
        if nidx >= 0:
            self._network.setCurrentIndex(nidx)
        self._farmer_host.setText(h.farmer_host or "")
        self._ssh_user.setText(h.ssh_user)
        self._ssh_key.setText(h.ssh_key_path)
        self._chia_root.setText(h.chia_root)
        self._chia_config.setText(h.chia_config_dir)
        self._version.setText(h.last_known_version or "")
        self._enabled.setChecked(h.enabled)

    def _on_role_changed(self) -> None:
        is_harvester = (
            self._role.currentData(Qt.ItemDataRole.UserRole) == NodeRole.HARVESTER.value
        )
        self._farmer_host.setEnabled(is_harvester)
        if not is_harvester:
            self._farmer_host.clear()

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SSH private key",
            "",
            "All files (*)",
        )
        if path:
            self._ssh_key.setText(path)

    def _build_harvester(self) -> Harvester:
        role = NodeRole(self._role.currentData(Qt.ItemDataRole.UserRole))
        network = ChiaNetwork(self._network.currentData(Qt.ItemDataRole.UserRole))
        farmer = self._farmer_host.text().strip() or None
        return Harvester(
            id=self._id.text().strip().lower(),
            display_name=self._display_name.text().strip()
            or self._id.text().strip().upper(),
            host=self._host.text().strip(),
            role=role,
            network=network,
            ssh_user=self._ssh_user.text().strip(),
            ssh_key_path=self._ssh_key.text().strip(),
            chia_root=self._chia_root.text().strip(),
            chia_config_dir=self._chia_config.text().strip(),
            last_known_version=self._version.text().strip() or None,
            farmer_host=farmer if role == NodeRole.HARVESTER else None,
            enabled=self._enabled.isChecked(),
        )

    def _save(self) -> None:
        h = self._build_harvester()
        errors = validate_node(h, self._existing, original_id=self._original_id)
        if errors:
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        self.result_harvester = h
        self.accept()

    def _test_ssh(self) -> None:
        h = self._build_harvester()
        errors = validate_node(h, self._existing, original_id=self._original_id)
        if errors:
            QMessageBox.warning(self, "Validation", "\n".join(errors))
            return
        if self._async_thread is None:
            QMessageBox.warning(self, "Test SSH", "Background worker not ready.")
            return

        def on_success(result: tuple[str, bool, BaseException | None]) -> None:
            _, ok, err = result
            if ok:
                QMessageBox.information(self, "Test SSH", f"Connected to {h.host} successfully.")
                return
            self._handle_ssh_failure(h, err)

        bridge = AsyncTaskBridge(self._async_thread, parent=self)
        bridge.succeeded.connect(on_success)
        bridge.failed.connect(lambda msg: self._handle_ssh_failure(h, msg))
        bridge.submit(node_test_ssh(h))

    def _handle_ssh_failure(
        self, h: Harvester, err: BaseException | str | None
    ) -> None:
        message, offer_passphrase = explain_ssh_failure(
            err,
            host=h.host,
            key_path=expand_key_path(h.ssh_key_path),
        )
        if not offer_passphrase:
            QMessageBox.warning(self, "Test SSH failed", message)
            return
        if not keyring_available():
            QMessageBox.warning(
                self,
                "Test SSH failed",
                message + "\n\nInstall keyring support: pip install -e \".[gui]\"",
            )
            return
        reply = QMessageBox.question(
            self,
            "Encrypted SSH key",
            message + "\n\nEnter passphrase now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        from PySide6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getText(
            self,
            "SSH key passphrase",
            "Passphrase (stored in system keyring):",
            echo=QLineEdit.EchoMode.Password,
        )
        if not ok or not text:
            return
        set_passphrase(h.ssh_key_path, text)
        self._test_ssh()
