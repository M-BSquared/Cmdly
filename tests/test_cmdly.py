"""Unit and integration test suite for Cmdly."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    ButtonConfig,
    CompanionConfig,
    SshConnection,
    TARGET_LOCAL,
    TARGET_SSH,
    MODE_TERMINAL,
    MODE_BACKGROUND,
    COMPANION_TARGET_PING,
    COMPANION_TARGET_SSH,
    terminal_line,
    preview_line,
    validate_host,
    validate_new_connection,
    derived_name,
    nearest_step,
    timeout_for,
    interval_for,
    INTERVAL_STEPS,
    TIMEOUT_STEPS,
)
from app.config import ConfigManager


class TestModels(unittest.TestCase):
    def test_derived_name(self):
        c1 = SshConnection(host="192.168.2.10", username="pilot")
        self.assertEqual(derived_name(c1), "pilot@192.168.2.10")

        c2 = SshConnection(host="192.168.2.10", username="")
        self.assertEqual(derived_name(c2), "192.168.2.10")

        c3 = SshConnection(host="", username="pilot")
        self.assertEqual(derived_name(c3), "")

    def test_validate_host(self):
        self.assertEqual(validate_host("192.168.2.10"), "")
        self.assertEqual(validate_host("drone-companion.local"), "")
        self.assertNotEqual(validate_host(""), "")
        self.assertNotEqual(validate_host("invalid host with spaces"), "")

    def test_validate_new_connection(self):
        c = SshConnection(host="10.0.0.1", port=22, name="conn1")
        self.assertEqual(validate_new_connection(c, []), "")
        self.assertIn("already saved", validate_new_connection(c, ["conn1"]))

        c_bad_port = SshConnection(host="10.0.0.1", port=70000, name="bad")
        self.assertIn("between 1 and 65535", validate_new_connection(c_bad_port, []))

    def test_terminal_line(self):
        b1 = ButtonConfig(command="python run.py", directory="~/mission")
        self.assertEqual(terminal_line(b1), "cd -- ~/'mission' && python run.py")

        b2 = ButtonConfig(command="ls -la", directory="")
        self.assertEqual(terminal_line(b2), "ls -la")

        b3 = ButtonConfig(command="pytest", directory="/tmp/test space")
        self.assertEqual(terminal_line(b3), "cd -- '/tmp/test space' && pytest")

    def test_preview_line(self):
        b_local_term = ButtonConfig(
            target=TARGET_LOCAL,
            mode=MODE_TERMINAL,
            directory="~/mission",
            command="./start.sh",
        )
        self.assertEqual(preview_line(b_local_term), "cd ~/mission && ./start.sh")

        b_local_bg = ButtonConfig(
            target=TARGET_LOCAL,
            mode=MODE_BACKGROUND,
            directory="~/mission",
            command="./start.sh",
        )
        self.assertEqual(preview_line(b_local_bg), "cd ~/mission && ./start.sh &")

        b_ssh_term = ButtonConfig(
            target=TARGET_SSH,
            connection="CORVUS-01",
            mode=MODE_TERMINAL,
            directory="/opt/flight",
            command="python main.py",
        )
        self.assertEqual(preview_line(b_ssh_term), "ssh CORVUS-01 'cd /opt/flight && python main.py'")

    def test_sliders_steps(self):
        self.assertEqual(nearest_step(INTERVAL_STEPS, 4, 2), 3)
        self.assertEqual(nearest_step(INTERVAL_STEPS, 8, 2), 10)
        self.assertGreater(timeout_for(5), 5)
        self.assertLess(interval_for(6), 6)


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load(self):
        mgr = ConfigManager(self.config_dir)
        btn = ButtonConfig(
            id="test1",
            label="Run Camera",
            target=TARGET_LOCAL,
            command="ffmpeg -i /dev/video0",
            mode=MODE_BACKGROUND,
        )
        mgr.save_button(btn)

        comp = CompanionConfig(
            name="Drone-01",
            host="192.168.1.50",
            type=COMPANION_TARGET_PING,
            interval_s=3,
            timeout_s=10,
        )
        mgr.set_companion(comp)

        conn = SshConnection(name="Pi", host="192.168.1.50", port=22, username="pi")
        mgr.save_connection(conn)

        # Reload in a new manager
        mgr2 = ConfigManager(self.config_dir)
        loaded_btns = mgr2.get_buttons()
        self.assertTrue(any(b.id == "test1" for b in loaded_btns))

        loaded_comp = mgr2.get_companion()
        self.assertIsNotNone(loaded_comp)
        self.assertEqual(loaded_comp.host, "192.168.1.50")
        self.assertEqual(loaded_comp.interval_s, 3)

        loaded_conns = mgr2.get_connections()
        self.assertEqual(len(loaded_conns), 1)
        self.assertEqual(loaded_conns[0].name, "Pi")


if __name__ == "__main__":
    unittest.main()
