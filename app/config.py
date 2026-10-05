"""Configuration storage and persistence for Cmdly (~/.cmdly/config.json)."""

import json
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.models import (
    ButtonConfig,
    CompanionConfig,
    SshConnection,
    MAX_BUTTONS,
    TARGET_LOCAL,
    MODE_TERMINAL,
)


class ConfigManager:
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            self.config_dir = Path.home() / ".cmdly"
        else:
            self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "config.json"
        self._ensure_dir()
        self.buttons: List[ButtonConfig] = []
        self.companion: Optional[CompanionConfig] = None
        self.connections: List[SshConnection] = []
        self.load()

    def _ensure_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def load(self):
        if not self.config_file.exists():
            self._create_default_config()
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}

        self.buttons = []
        raw_buttons = data.get("buttons", [])
        if isinstance(raw_buttons, list):
            for rb in raw_buttons:
                btn = ButtonConfig.from_dict(rb)
                if btn and len(self.buttons) < MAX_BUTTONS:
                    self.buttons.append(btn)

        raw_comp = data.get("companion")
        self.companion = CompanionConfig.from_dict(raw_comp) if raw_comp else None

        self.connections = []
        raw_conns = data.get("connections", [])
        if isinstance(raw_conns, list):
            for rc in raw_conns:
                conn = SshConnection.from_dict(rc)
                if conn.name:
                    self.connections.append(conn)

    def _create_default_config(self):
        # Sample starter button so the user sees how it works right away
        self.buttons = [
            ButtonConfig(
                id="b_welcome",
                label="System Info",
                target=TARGET_LOCAL,
                connection="",
                directory="~",
                command="uname -a && uptime",
                mode=MODE_TERMINAL,
                restart=False,
            )
        ]
        self.companion = None
        self.connections = []
        self.save()

    def save(self):
        self._ensure_dir()
        data = {
            "buttons": [b.to_dict() for b in self.buttons],
            "companion": self.companion.to_dict() if self.companion else None,
            "connections": [c.to_dict() for c in self.connections],
        }
        # Atomic write
        tmp_file = self.config_file.with_suffix(".tmp")
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp_file.replace(self.config_file)
        except Exception as e:
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)
            raise e

    def get_buttons(self) -> List[ButtonConfig]:
        return list(self.buttons)

    def save_button(self, button: ButtonConfig):
        for idx, b in enumerate(self.buttons):
            if b.id == button.id:
                self.buttons[idx] = button
                self.save()
                return
        if len(self.buttons) < MAX_BUTTONS:
            self.buttons.append(button)
            self.save()

    def delete_button(self, button_id: str):
        self.buttons = [b for b in self.buttons if b.id != button_id]
        self.save()

    def get_companion(self) -> Optional[CompanionConfig]:
        return self.companion

    def set_companion(self, companion: Optional[CompanionConfig]):
        self.companion = companion
        self.save()

    def get_connections(self) -> List[SshConnection]:
        return list(self.connections)

    def get_connection_by_name(self, name: str) -> Optional[SshConnection]:
        for c in self.connections:
            if c.name == name:
                return c
        return None

    def save_connection(self, connection: SshConnection):
        for idx, c in enumerate(self.connections):
            if c.name == connection.name:
                self.connections[idx] = connection
                self.save()
                return
        self.connections.append(connection)
        self.save()

    def delete_connection(self, name: str):
        self.connections = [c for c in self.connections if c.name != name]
        self.save()
