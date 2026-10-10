import sys
import time
import random
import threading
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QCoreApplication
from PyQt6.QtGui import QIcon, QFont, QColor, QPalette
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, 
    QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QComboBox, 
    QRadioButton, QCheckBox, QSpinBox, QSystemTrayIcon, QMenu, QMessageBox
)
from pynput.mouse import Controller as MouseController, Button
from pynput import keyboard

# Modern Dark Theme QSS Stylesheet
DARK_STYLE = """
QMainWindow {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QGroupBox {
    background-color: #252538;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: bold;
    color: #89b4fa;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #252538;
}
QLabel {
    color: #cdd6f4;
    font-size: 13px;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}
QPushButton:pressed {
    background-color: #585b70;
}
QComboBox, QSpinBox {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: #89b4fa;
}
QRadioButton, QCheckBox {
    color: #cdd6f4;
    spacing: 8px;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
"""

class ClickerWorker(QThread):
    status_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.mouse = MouseController()
        self.running = False
        self.mode = "Toggle" # Toggle or Hold
        self.cps = 10.0
        self.min_wait_ms = 0
        self.human_cadence = False
        self.jitter_ms = 0

    def run(self):
        while True:
            if self.running:
                start_time = time.time()
                
                # Perform click
                try:
                    self.mouse.click(Button.left, 1)
                except Exception:
                    pass

                # Calculate delay based on CPS
                base_delay = 1.0 / max(self.cps, 0.1)
                
                # Apply minimum wait time
                if self.min_wait_ms > 0:
                    base_delay = max(base_delay, self.min_wait_ms / 1000.0)

                # Apply humanizing jitter
                if self.human_cadence and self.jitter_ms > 0:
                    jitter = random.uniform(-self.jitter_ms, self.jitter_ms) / 1000.0
                    base_delay = max(0.001, base_delay + jitter)

                elapsed = time.time() - start_time
                sleep_time = base_delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    time.sleep(0.001)
            else:
                time.sleep(0.05)


class AutoClickerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Auto-Clicker Pro")
        self.setFixedSize(460, 620)
        
        # Clicker Engine Thread
        self.clicker_worker = ClickerWorker()
        self.clicker_worker.start()

        # State Variables
        self.trigger_key = 'F6'
        self.is_active = False
        self.is_rebind_mode = False

        self.init_ui()
        self.init_system_tray()
        self.init_hotkey_listener()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Status Header
        status_layout = QHBoxLayout()
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #f38ba8; font-size: 18px;") # Red by default
        self.status_label = QLabel("Status: STOPPED")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #f38ba8;")
        status_layout.addWidget(self.status_indicator)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # 1. Configure Trigger Panel
        trigger_group = QGroupBox("1. Configure Trigger")
        trigger_layout = QHBoxLayout()
        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(['F6', 'F7', 'F8', 'F9', 'F10', 'F11', 'F12', 'Space', 'Ctrl', 'Shift'])
        self.rebind_btn = QPushButton("Rebind Key")
        self.rebind_btn.clicked.connect(self.start_rebind)
        trigger_layout.addWidget(QLabel("Trigger Key:"))
        trigger_layout.addWidget(self.trigger_combo)
        trigger_layout.addWidget(self.rebind_btn)
        trigger_group.setLayout(trigger_layout)
        main_layout.addWidget(trigger_group)

        # 2. Activation Mode Panel
        mode_group = QGroupBox("2. Activation Mode")
        mode_layout = QHBoxLayout()
        self.radio_toggle = QRadioButton("Toggle (Press to Start/Stop)")
        self.radio_hold = QRadioButton("Hold (Click while pressed)")
        self.radio_toggle.setChecked(True)
        mode_layout.addWidget(self.radio_toggle)
        mode_layout.addWidget(self.radio_hold)
        mode_group.setLayout(mode_layout)
        main_layout.addWidget(mode_group)

        # 3. Click Speed & Timing Panel
        timing_group = QGroupBox("3. Click Speed & Timing")
        timing_layout = QGridLayout()
        
        self.cps_spin = QSpinBox()
        self.cps_spin.setRange(1, 1000)
        self.cps_spin.setValue(15)
        self.cps_spin.valueChanged.connect(self.update_settings)

        self.min_wait_spin = QSpinBox()
        self.min_wait_spin.setRange(0, 5000)
        self.min_wait_spin.setValue(0)
        self.min_wait_spin.setSuffix(" ms")
        self.min_wait_spin.valueChanged.connect(self.update_settings)

        timing_layout.addWidget(QLabel("Clicks Per Second (CPS):"), 0, 0)
        timing_layout.addWidget(self.cps_spin, 0, 1)
        timing_layout.addWidget(QLabel("Minimum Wait Time:"), 1, 0)
        timing_layout.addWidget(self.min_wait_spin, 1, 1)
        timing_group.setLayout(timing_layout)
        main_layout.addWidget(timing_group)

        # 4. Pattern & Humanizing Panel
        human_group = QGroupBox("4. Pattern & Humanizing")
        human_layout = QGridLayout()
        
        self.human_check = QCheckBox("Enable Human-Like Cadence")
        self.human_check.stateChanged.connect(self.update_settings)
        
        self.jitter_spin = QSpinBox()
        self.jitter_spin.setRange(1, 200)
        self.jitter_spin.setValue(15)
        self.jitter_spin.setSuffix(" ms")
        self.jitter_spin.valueChanged.connect(self.update_settings)

        human_layout.addWidget(self.human_check, 0, 0, 1, 2)
        human_layout.addWidget(QLabel("Randomized Jitter:"), 1, 0)
        human_layout.addWidget(self.jitter_spin, 1, 1)
        human_group.setLayout(human_layout)
        main_layout.addWidget(human_group)

        # 5. General Settings Panel
        general_group = QGroupBox("5. General Settings")
        general_layout = QVBoxLayout()
        self.tray_check = QCheckBox("Minimize to System Tray")
        self.tray_check.setChecked(True)
        general_layout.addWidget(self.tray_check)
        general_group.setLayout(general_layout)
        main_layout.addWidget(general_group)

        self.update_settings()

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        # Creating a placeholder programmatic icon
        self.tray_icon.setIcon(self.style().standardIcon(QApplication.style().StandardPixmap.SP_ComputerIcon))
        
        tray_menu = QMenu()
        restore_action = tray_menu.addAction("Open Auto-Clicker")
        restore_action.triggered.connect(self.showNormal)
        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(QCoreApplication.quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()
                self.activateWindow()

    def closeEvent(self, event):
        if self.tray_check.isChecked() and self.tray_icon.isVisible():
            self.hide()
            self.tray_icon.showMessage(
                "Auto-Clicker Running",
                "Application minimized to system tray. Double-click tray icon or right-click to exit.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )
            event.ignore()
        else:
            self.clicker_worker.terminate()
            event.accept()

    def init_hotkey_listener(self):
        def on_press(key):
            if self.is_rebind_mode:
                key_name = self.parse_key_name(key)
                if key_name:
                    self.trigger_key = key_name
                    self.trigger_combo.setCurrentText(key_name)
                    self.is_rebind_mode = False
                    self.rebind_btn.setText("Rebind Key")
                    self.rebind_btn.setStyleSheet("")
                return

            current_target = self.trigger_combo.currentText()
            matched = False
            try:
                if hasattr(key, 'name') and key.name.upper() == current_target.upper():
                    matched = True
                elif hasattr(key, 'char') and key.char and key.char.upper() == current_target.upper():
                    matched = True
            except Exception:
                pass

            if matched:
                if self.radio_toggle.isChecked():
                    self.toggle_clicking_state()
                elif self.radio_hold.isChecked():
                    self.set_clicking_state(True)

        def on_release(key):
            if self.radio_hold.isChecked() and not self.is_rebind_mode:
                current_target = self.trigger_combo.currentText()
                matched = False
                try:
                    if hasattr(key, 'name') and key.name.upper() == current_target.upper():
                        matched = True
                    elif hasattr(key, 'char') and key.char and key.char.upper() == current_target.upper():
                        matched = True
                except Exception:
                    pass
                if matched:
                    self.set_clicking_state(False)

        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.listener.daemon = True
        self.listener.start()

    def parse_key_name(self, key):
        try:
            if hasattr(key, 'name'):
                return key.name.upper()
            elif hasattr(key, 'char') and key.char:
                return key.char.upper()
        except Exception:
            pass
        return None

    def start_rebind(self):
        self.is_rebind_mode = True
        self.rebind_btn.setText("Press any key...")
        self.rebind_btn.setStyleSheet("background-color: #fab387; color: #1e1e2e;")

    def toggle_clicking_state(self):
        new_state = not self.is_active
        self.set_clicking_state(new_state)

    def set_clicking_state(self, state):
        self.is_active = state
        self.clicker_worker.running = state
        
        # Update UI safely from main thread
        if state:
            self.status_indicator.setStyleSheet("color: #a6e3a1; font-size: 18px;")
            self.status_label.setText("Status: STARTED")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #a6e3a1;")
        else:
            self.status_indicator.setStyleSheet("color: #f38ba8; font-size: 18px;")
            self.status_label.setText("Status: STOPPED")
            self.status_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #f38ba8;")

    def update_settings(self):
        self.clicker_worker.cps = float(self.cps_spin.value())
        self.clicker_worker.min_wait_ms = self.min_wait_spin.value()
        self.clicker_worker.human_cadence = self.human_check.isChecked()
        self.clicker_worker.jitter_ms = self.jitter_spin.value()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = AutoClickerWindow()
    window.setStyleSheet(DARK_STYLE)
    window.show()
    
    sys.exit(app.exec())