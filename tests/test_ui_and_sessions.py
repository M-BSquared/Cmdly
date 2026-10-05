"""Integration tests for UI widgets and local sessions."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Set offscreen Qt platform for headless testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from app.config import ConfigManager
from app.models import ButtonConfig, TARGET_LOCAL, MODE_TERMINAL
from app.sessions.local_session import LocalSession
from app.ui.main_window import MainWindow
from app.ui.widgets.terminal_widget import ansi_to_html

app = QApplication.instance() or QApplication(sys.argv)


class TestUiAndSessions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.config_mgr = ConfigManager(self.config_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ansi_to_html(self):
        colored = "\x1b[32mSuccess\x1b[0m and \x1b[31mError\x1b[0m"
        converted = ansi_to_html(colored)
        self.assertIn("color: #2ec971;", converted)
        self.assertIn("color: #eb4d4b;", converted)
        self.assertIn("Success", converted)
        self.assertIn("Error", converted)

    def test_local_session_execution(self):
        received_output = []
        session = LocalSession("test_local", "Test Shell")
        session.output_received.connect(lambda text: received_output.append(text))

        started = session.start()
        self.assertTrue(started, "LocalSession should start successfully on posix")
        self.assertTrue(session.is_alive())

        # Send an echo command
        session.send("echo CMDLY_TEST_TOKEN\n")

        # Wait briefly for reader thread to pick up output
        t0 = time.time()
        found = False
        while time.time() - t0 < 3.0:
            app.processEvents()
            all_text = "".join(received_output)
            if "CMDLY_TEST_TOKEN" in all_text:
                found = True
                break
            time.sleep(0.05)

        self.assertTrue(found, f"Output should contain CMDLY_TEST_TOKEN, got: {''.join(received_output)}")
        session.stop()
        self.assertFalse(session.is_alive())

    def test_main_window_lifecycle(self):
        window = MainWindow(self.config_mgr)
        self.assertIsNotNone(window)
        app.processEvents()

        # Check that starter button is rendered in shelf
        buttons = self.config_mgr.get_buttons()
        self.assertGreater(len(buttons), 0)
        btn_id = buttons[0].id
        self.assertIn(btn_id, window.shelf_view.row_widgets)

        window.close()

    def test_ticked_slider(self):
        from app.ui.widgets.ticked_slider import TickedSlider
        slider = TickedSlider([1, 2, 3, 5, 10], initial_value=2)
        self.assertEqual(slider.value(), 2)

        slider.setValue(5)
        self.assertEqual(slider.value(), 5)

        slider.setIndex(0)
        self.assertEqual(slider.value(), 1)

    def test_terminal_window(self):
        from app.ui.dialogs.terminal_window import TerminalWindow
        win = TerminalWindow("test_sess", title="ls", host="this computer")
        self.assertEqual(win.session_id, "test_sess")
        self.assertEqual(win.title_label.text(), "ls")
        self.assertEqual(win.host_label.text(), "this computer")

        win.append_output("hello terminal")
        self.assertIn("hello terminal", win.output_area.toPlainText())

        win.set_connected(True)
        self.assertEqual(win.status_text.text(), "CONNECTED")
        win.close()

    def test_companion_modal(self):
        from app.ui.widgets.companion_modal import CompanionModalWidget
        from app.models import CompanionConfig
        comp = CompanionConfig(name="TestComp", host="192.168.1.99")
        modal = CompanionModalWidget(comp, [])
        self.assertEqual(modal.interval_slider.value(), 2)
        self.assertEqual(modal.timeout_slider.value(), 6)

    def test_settings_modal_and_themes(self):
        from app.ui.widgets.settings_modal import SettingsModalWidget
        from app.ui.styles import theme_manager
        modal = SettingsModalWidget(self.config_mgr)
        self.assertIsNotNone(modal)

        # Select midnight theme
        modal._select_theme("midnight")
        self.assertEqual(self.config_mgr.get_theme(), "midnight")
        self.assertEqual(theme_manager.current_theme_id, "midnight")

        # Select apple_dark theme
        modal._select_theme("apple_dark")
        self.assertEqual(self.config_mgr.get_theme(), "apple_dark")
        self.assertEqual(theme_manager.current_theme_id, "apple_dark")

    def test_main_window_bottom_bar_and_resizability(self):
        from app.ui.main_window import MainWindow
        win = MainWindow(self.config_mgr)
        self.assertGreaterEqual(win.minimumWidth(), 380)
        self.assertGreaterEqual(win.minimumHeight(), 440)
        self.assertTrue(win.settings_btn.isEnabled())
        self.assertIn("Profile", win.counter_label.text())
        win.close()


if __name__ == "__main__":
    unittest.main()
