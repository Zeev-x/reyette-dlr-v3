import os
import sys
import threading
import contextlib
import io

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit,
        QPushButton, QComboBox, QTextEdit
    )
    from PyQt6.QtGui import QTextCursor, QIcon, QFont
    from PyQt6.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot
except ModuleNotFoundError as exc:
    print("Error: modul PyQt6 belum terinstal untuk interpreter Python ini.")
    print("Silakan jalankan:")
    print("python -m pip install -r requirements.txt")
    raise SystemExit(1) from exc

import downloader


def find_app_icon():
    asset_paths = (
        os.path.join("icon", "icon.ico"),
        os.path.join("logo", "logo.png"),
    )
    base_paths = (
        getattr(sys, "_MEIPASS", None),
        os.path.dirname(os.path.abspath(__file__)),
        os.path.dirname(os.path.abspath(sys.executable)),
    )

    for base_path in base_paths:
        if not base_path:
            continue
        for asset_path in asset_paths:
            candidate = os.path.join(base_path, asset_path)
            if os.path.isfile(candidate):
                return candidate
    return None


class StreamLogger(io.StringIO):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui

    def write(self, text):
        if not text:
            return

        cleaned = text.rstrip("\n")
        if not cleaned.strip():
            return

        if "\r" in cleaned:
            last_chunk = cleaned.split("\r")[-1].strip()
            if last_chunk:
                self.ui.post_log(last_chunk)
        else:
            self.ui.post_log(cleaned.strip())


class DownloaderUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Premium Downloader")
        self.setGeometry(200, 200, 760, 560)
        self.setMinimumSize(620, 480)

        icon_path = find_app_icon()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        layout = QVBoxLayout()
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(16)

        title = QLabel("Premium Downloader")
        title_font = QFont("Segoe UI", 30, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Unduh video dan audio dengan mudah")
        subtitle.setObjectName("subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        url_label = QLabel("URL")
        url_label.setObjectName("fieldLabel")
        layout.addWidget(url_label)

        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText("Masukkan URL (YouTube, TikTok, Facebook, Instagram, Twitter/X)")
        layout.addWidget(self.url_input)

        mode_label = QLabel("FORMAT")
        mode_label.setObjectName("fieldLabel")
        layout.addWidget(mode_label)

        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("modeCombo")
        self.mode_combo.addItems(["MP3", "MP4"])
        self.mode_combo.setCurrentText("MP3")
        layout.addWidget(self.mode_combo)

        self.quality_label = QLabel("KUALITAS")
        self.quality_label.setObjectName("fieldLabel")
        layout.addWidget(self.quality_label)

        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("qualityCombo")
        self.quality_combo.addItems(["360p", "480p", "720p", "1080p", "MAX"])
        self.quality_combo.setCurrentText("720p")
        layout.addWidget(self.quality_combo)
        self.mode_combo.currentTextChanged.connect(self._update_quality_visibility)
        self._update_quality_visibility(self.mode_combo.currentText())

        self.download_btn = QPushButton("DOWNLOAD")
        self.download_btn.setObjectName("downloadButton")
        self.download_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)

        log_label = QLabel("AKTIVITAS")
        log_label.setObjectName("fieldLabel")
        layout.addWidget(log_label)

        self.log_area = QTextEdit()
        self.log_area.setObjectName("logArea")
        self.log_area.setFont(QFont("Consolas", 11))
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("Status unduhan akan muncul di sini...")
        self._log_lines = []
        layout.addWidget(self.log_area)

        self.setLayout(layout)

        self.setStyleSheet("""QWidget {
    background-color: #0B1020;
    color: #E5E7EB;
    font-family: 'Segoe UI';
}

QLabel#subtitle {
    color: #94A3B8;
    padding-bottom: 8px;
}

QLabel#fieldLabel {
    color: #94A3B8;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}

QLineEdit, QComboBox, QTextEdit {
    background-color: #141B2D;
    border: 1px solid #26324A;
    border-radius: 10px;
    padding: 11px 12px;
    color: #F8FAFC;
    selection-background-color: #4F7DFF;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #4F7DFF;
}

QComboBox QAbstractItemView {
    background-color: #141B2D;
    color: #F8FAFC;
    selection-background-color: #315FEA;
    selection-color: #FFFFFF;
    border: 1px solid #26324A;
    outline: 0;
}

QPushButton#downloadButton {
    background-color: #4F7DFF;
    border: none;
    border-radius: 10px;
    padding: 13px 16px;
    color: #FFFFFF;
}

QPushButton#downloadButton:hover {
    background-color: #6790FF;
}

QPushButton#downloadButton:pressed {
    background-color: #3B68E8;
}

QPushButton#downloadButton:disabled {
    background-color: #26324A;
    color: #7C879B;
}

QTextEdit#logArea {
    background-color: #0E1525;
    border: 1px solid #26324A;
    border-radius: 10px;
    padding: 12px;
}
        """)

    def _update_quality_visibility(self, mode):
        show_quality = mode.upper() != "MP3"
        self.quality_label.setVisible(show_quality)
        self.quality_combo.setVisible(show_quality)

    def start_download(self):
        url = self.url_input.text().strip()
        mode = self.mode_combo.currentText()
        quality = self.quality_combo.currentText()

        if not url:
            self.post_log("URL kosong!")
            return

        self.log_area.clear()
        self._log_lines = []
        self._set_button_enabled(False)

        thread = threading.Thread(target=self._download_thread, args=(url, mode, quality), daemon=True)
        thread.start()

    def post_log(self, message):
        if not message:
            return
        QMetaObject.invokeMethod(self, "_append_log", Qt.ConnectionType.QueuedConnection, Q_ARG(str, message))

    def _is_progress_message(self, message):
        lowered = message.lower()
        return '%' in message or 'encoding progres' in lowered or 'time=' in lowered or 'frame=' in lowered or 'fps=' in lowered or 'size=' in lowered

    @pyqtSlot(str)
    def _append_log(self, message):
        if self._is_progress_message(message):
            if self._log_lines and self._log_lines[-1].startswith('[RYDL] '):
                self._log_lines[-1] = f'[RYDL] {message}'
            else:
                self._log_lines.append(f'[RYDL] {message}')
        else:
            self._log_lines.append(message)

        self.log_area.setPlainText('\n'.join(self._log_lines))
        self.log_area.moveCursor(QTextCursor.MoveOperation.End)

    def _set_button_enabled(self, enabled):
        QMetaObject.invokeMethod(self, "_apply_button_enabled", Qt.ConnectionType.QueuedConnection, Q_ARG(bool, enabled))

    @pyqtSlot(bool)
    def _apply_button_enabled(self, enabled):
        self.download_btn.setEnabled(enabled)

    def _download_thread(self, url, mode, quality):
        stdout_logger = StreamLogger(self)
        stderr_logger = StreamLogger(self)

        try:
            with contextlib.redirect_stdout(stdout_logger), contextlib.redirect_stderr(stderr_logger):
                success = downloader.run_download(url, mode, quality)
            if not success:
                self.post_log("Download selesai dengan kesalahan.")
        except Exception as e:
            self.post_log(f"Error internal: {e}")
        finally:
            self._set_button_enabled(True)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 12))
    ui = DownloaderUI()
    ui.show()
    sys.exit(app.exec())