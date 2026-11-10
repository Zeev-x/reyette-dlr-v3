import os
import sys
import threading
import contextlib
import io
import re

try:
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
        QPushButton, QComboBox, QTextEdit, QFrame, QStackedWidget,
        QSlider, QColorDialog, QProgressBar, QStyle
    )
    from PyQt6.QtGui import QTextCursor, QIcon, QFont, QPixmap, QColor, QPainter, QPen
    from PyQt6.QtCore import Qt, QMetaObject, Q_ARG, pyqtSlot, QSettings, QEvent, QSize
except ModuleNotFoundError as exc:
    print("Error: modul PyQt6 belum terinstal untuk interpreter Python ini.")
    print("Silakan jalankan:")
    print("python -m pip install -r requirements.txt")
    raise SystemExit(1) from exc

import downloader


def find_app_icon():
    asset_paths = (
        os.path.join("icon", "icon.png"),
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

        for line in re.split(r"[\r\n]+", text):
            cleaned = line.strip()
            if cleaned:
                self.ui.post_log(cleaned)


class DownloaderUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Premium Downloader")
        self.setGeometry(200, 200, 980, 680)
        self.setMinimumSize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("windowRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._drag_offset = None
        self.settings = QSettings("Reyette", "PremiumDownloader")
        self.accent_color = self.settings.value("ui/accent_color", "#6C8CFF", type=str)
        self.surface_color = self.settings.value("ui/surface_color", "#101827", type=str)
        self.background_opacity = self.settings.value("ui/background_opacity", 82, type=int)

        icon_path = find_app_icon()
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(10, 10, 10, 10)
        surface = QFrame()
        surface.setObjectName("appSurface")
        outer_layout.addWidget(surface)

        surface_layout = QHBoxLayout(surface)
        surface_layout.setContentsMargins(0, 0, 0, 0)
        surface_layout.setSpacing(0)
        surface_layout.addWidget(self._build_sidebar())

        content = QFrame()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(34, 30, 34, 30)
        content_layout.setSpacing(22)
        surface_layout.addWidget(content, 1)

        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_bar_layout = QHBoxLayout(title_bar)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_bar_layout.setSpacing(8)
        self.page_heading = QLabel()
        self.page_heading.setObjectName("pageHeading")
        title_bar_layout.addWidget(self.page_heading, 1)
        title_bar_layout.addStretch(1)
        minimize_button = QPushButton()
        minimize_button.setObjectName("windowButton")
        minimize_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMinButton)
        )
        minimize_button.setIconSize(QSize(16, 16))
        minimize_button.setToolTip("Minimize")
        minimize_button.clicked.connect(self.showMinimized)
        self.maximize_button = QPushButton()
        self.maximize_button.setObjectName("windowButton")
        self.maximize_button.setIconSize(QSize(16, 16))
        self.maximize_button.setToolTip("Maximize / windowed")
        self.maximize_button.clicked.connect(self._toggle_maximized)
        maximize_button = self.maximize_button
        self._update_maximize_icon()
        close_button = QPushButton()
        close_button.setObjectName("closeButton")
        close_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )
        close_button.setIconSize(QSize(16, 16))
        close_button.setToolTip("Close")
        close_button.clicked.connect(self.close)
        title_bar_layout.addWidget(minimize_button)
        title_bar_layout.addWidget(maximize_button)
        title_bar_layout.addWidget(close_button)
        title_bar.installEventFilter(self)
        self.page_heading.installEventFilter(self)
        content_layout.addWidget(title_bar)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_download_page())
        self.pages.addWidget(self._build_log_page())
        self.pages.addWidget(self._build_settings_page())
        content_layout.addWidget(self.pages, 1)
        self._show_page(0)

        self.apply_theme()

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 28, 16, 20)
        layout.setSpacing(12)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        icon_path = find_app_icon()
        logo = QLabel()
        logo.setObjectName("brandLogo")
        if icon_path:
            logo.setPixmap(QPixmap(icon_path).scaled(
                48, 48, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
        else:
            logo.setText("PD")
            logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(logo)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        brand_title = QLabel("PREMIUM")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel("DOWNLOADER")
        brand_subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)
        brand.addLayout(brand_text)
        layout.addLayout(brand)
        layout.addSpacing(36)

        self.nav_buttons = []
        for index, (text, icon_name) in enumerate((
            ("Download", "download"),
            ("Log aktivitas", "log"),
            ("Pengaturan", "settings"),
        )):
            button = QPushButton(text)
            button.setObjectName("navButton")
            button.setIconSize(QSize(20, 20))
            button.setToolTip(text)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked, page=index: self._on_nav_clicked(page, checked)
            )
            layout.addWidget(button)
            self.nav_buttons.append(button)
            button.setProperty("iconName", icon_name)

        layout.addStretch(1)
        footer = QLabel("MEDIA DOWNLOADER")
        footer.setObjectName("sidebarFooter")
        layout.addWidget(footer)
        return sidebar

    def _build_download_page(self):
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(18)

        intro = QLabel("Tempel tautan media yang ingin kamu simpan.")
        intro.setObjectName("subtitle")
        page_layout.addWidget(intro)

        card = QFrame()
        card.setObjectName("contentCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(24, 24, 24, 24)
        form.setSpacing(12)

        url_label = QLabel("TAUTAN MEDIA")
        url_label.setObjectName("fieldLabel")
        form.addWidget(url_label)
        self.url_input = QLineEdit()
        self.url_input.setObjectName("urlInput")
        self.url_input.setPlaceholderText(
            "YouTube, TikTok, Facebook, Instagram, Twitter/X..."
        )
        form.addWidget(self.url_input)

        options = QHBoxLayout()
        options.setSpacing(16)
        mode_column = QVBoxLayout()
        mode_column.setSpacing(9)
        mode_label = QLabel("FORMAT")
        mode_label.setObjectName("fieldLabel")
        mode_column.addWidget(mode_label)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("modeCombo")
        self.mode_combo.addItems(["MP3", "MP4"])
        self.mode_combo.setCurrentText("MP3")
        mode_column.addWidget(self.mode_combo)
        options.addLayout(mode_column)

        quality_column = QVBoxLayout()
        quality_column.setSpacing(9)
        self.quality_label = QLabel("KUALITAS")
        self.quality_label.setObjectName("fieldLabel")
        quality_column.addWidget(self.quality_label)
        self.quality_combo = QComboBox()
        self.quality_combo.setObjectName("qualityCombo")
        self.quality_combo.addItems(["360p", "480p", "720p", "1080p", "MAX"])
        self.quality_combo.setCurrentText("720p")
        quality_column.addWidget(self.quality_combo)
        options.addLayout(quality_column)
        form.addLayout(options)
        self.mode_combo.currentTextChanged.connect(self._update_quality_visibility)
        self._update_quality_visibility(self.mode_combo.currentText())

        self.download_btn = QPushButton("DOWNLOAD")
        self.download_btn.setObjectName("downloadButton")
        self.download_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_btn.clicked.connect(self.start_download)
        form.addSpacing(8)
        form.addWidget(self.download_btn)
        page_layout.addWidget(card)

        progress_card = QFrame()
        progress_card.setObjectName("contentCard")
        self.download_progress_card = progress_card
        self.download_progress_card.hide()
        progress_layout = QVBoxLayout(progress_card)
        progress_layout.setContentsMargins(24, 20, 24, 20)
        progress_layout.setSpacing(12)
        self.progress_heading = QLabel("Menyiapkan unduhan")
        self.progress_heading.setObjectName("fieldLabel")
        progress_layout.addWidget(self.progress_heading)
        self.download_progress = QProgressBar()
        self.download_progress.setObjectName("downloadProgress")
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFormat("%p%")
        progress_layout.addWidget(self.download_progress)
        page_layout.addWidget(progress_card)
        note = QLabel("Detail proses tersedia di halaman Log aktivitas.")
        note.setObjectName("subtitle")
        page_layout.addWidget(note)
        page_layout.addStretch(1)
        return page

    def _build_log_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        subtitle = QLabel("Progres dan pesan dari proses unduhan.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)
        self.log_area = QTextEdit()
        self.log_area.setObjectName("logArea")
        self.log_area.setFont(QFont("Consolas", 11))
        self.log_area.setReadOnly(True)
        self.log_area.setPlaceholderText("Status unduhan akan muncul di sini...")
        self._log_lines = []
        layout.addWidget(self.log_area, 1)
        return page

    def _build_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        subtitle = QLabel("Sesuaikan tampilan aplikasi dengan desktop kamu.")
        subtitle.setObjectName("subtitle")
        layout.addWidget(subtitle)

        colors_card = QFrame()
        colors_card.setObjectName("contentCard")
        colors_layout = QVBoxLayout(colors_card)
        colors_layout.setContentsMargins(22, 20, 22, 20)
        colors_layout.setSpacing(14)
        colors_title = QLabel("Warna tampilan")
        colors_title.setObjectName("cardTitle")
        colors_layout.addWidget(colors_title)
        colors_layout.addWidget(self._create_color_row(
            "Warna aksen", "ui/accent_color", "accentColorButton"
        ))
        colors_layout.addWidget(self._create_color_row(
            "Warna permukaan", "ui/surface_color", "surfaceColorButton"
        ))
        layout.addWidget(colors_card)

        opacity_card = QFrame()
        opacity_card.setObjectName("contentCard")
        opacity_layout = QVBoxLayout(opacity_card)
        opacity_layout.setContentsMargins(22, 20, 22, 20)
        opacity_layout.setSpacing(12)
        opacity_heading = QHBoxLayout()
        opacity_title = QLabel("Transparansi latar")
        opacity_title.setObjectName("cardTitle")
        self.opacity_value = QLabel()
        self.opacity_value.setObjectName("opacityValue")
        opacity_heading.addWidget(opacity_title)
        opacity_heading.addStretch(1)
        opacity_heading.addWidget(self.opacity_value)
        opacity_layout.addLayout(opacity_heading)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(35, 100)
        self.opacity_slider.setValue(max(35, min(100, self.background_opacity)))
        self.opacity_slider.valueChanged.connect(self._update_opacity)
        opacity_layout.addWidget(self.opacity_slider)
        opacity_hint = QLabel("Nilai lebih rendah membuat wallpaper desktop lebih terlihat.")
        opacity_hint.setObjectName("subtitle")
        opacity_layout.addWidget(opacity_hint)
        layout.addWidget(opacity_card)

        reset_button = QPushButton("KEMBALIKAN TAMPILAN DEFAULT")
        reset_button.setObjectName("secondaryButton")
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.clicked.connect(self._reset_theme)
        layout.addWidget(reset_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _create_color_row(self, label_text, setting_key, object_name):
        row = QHBoxLayout()
        label = QLabel(label_text)
        button = QPushButton()
        button.setObjectName(object_name)
        button.setMinimumWidth(118)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: self._choose_color(setting_key))
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(button)
        return self._layout_widget(row)

    @staticmethod
    def _layout_widget(layout):
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    @staticmethod
    def _contrast_text_color(background):
        color = QColor(background)
        channels = []
        for channel in (color.redF(), color.greenF(), color.blueF()):
            channels.append(
                channel / 12.92 if channel <= 0.04045
                else ((channel + 0.055) / 1.055) ** 2.4
            )
        luminance = (
            0.2126 * channels[0] +
            0.7152 * channels[1] +
            0.0722 * channels[2]
        )
        return "#111827" if luminance > 0.179 else "#F8FAFC"

    def _show_page(self, index):
        headings = (
            ("WORKSPACE", "Siap untuk mengunduh"),
            ("AKTIVITAS", "Log unduhan"),
            ("PERSONALISASI", "Pengaturan tampilan"),
        )
        heading_color = self._contrast_text_color(self.surface_color)
        accent_text_color = self._contrast_text_color(self.accent_color)
        self.pages.setCurrentIndex(index)
        self.page_heading.setText(
            f'<span style="font-size:10px; color:{heading_color}; letter-spacing:2px;">'
            f'{headings[index][0]}</span><br>'
            f'<span style="font-size:25px; font-weight:700; color:{heading_color};">'
            f'{headings[index][1]}</span>'
        )
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
            icon_color = accent_text_color if button_index == index else "#A7B3C7"
            button.setIcon(self._create_navigation_icon(
                button.property("iconName"), icon_color
            ))

    def _create_navigation_icon(self, icon_name, color):
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))

        if icon_name == "download":
            painter.drawLine(12, 3, 12, 15)
            painter.drawLine(7, 10, 12, 15)
            painter.drawLine(17, 10, 12, 15)
            painter.drawLine(5, 17, 5, 20)
            painter.drawLine(5, 20, 19, 20)
            painter.drawLine(19, 20, 19, 17)
        elif icon_name == "log":
            painter.drawRoundedRect(4, 3, 16, 18, 2, 2)
            painter.drawLine(8, 8, 16, 8)
            painter.drawLine(8, 12, 16, 12)
            painter.drawLine(8, 16, 14, 16)
        else:
            painter.drawEllipse(9, 9, 6, 6)
            for x1, y1, x2, y2 in (
                (12, 2, 12, 6), (12, 18, 12, 22),
                (2, 12, 6, 12), (18, 12, 22, 12),
                (5, 5, 8, 8), (16, 16, 19, 19),
                (5, 19, 8, 16), (16, 8, 19, 5),
            ):
                painter.drawLine(x1, y1, x2, y2)
        painter.end()
        return QIcon(pixmap)

    def _update_maximize_icon(self):
        icon_name = (
            QStyle.StandardPixmap.SP_TitleBarNormalButton
            if self.isMaximized()
            else QStyle.StandardPixmap.SP_TitleBarMaxButton
        )
        self.maximize_button.setIcon(self.style().standardIcon(icon_name))

    def _on_nav_clicked(self, index, checked):
        if not checked:
            self.nav_buttons[index].setChecked(True)
        self._show_page(index)

    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._update_maximize_icon()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and hasattr(
            self, "maximize_button"
        ):
            self._update_maximize_icon()

    def eventFilter(self, watched, event):
        if watched.objectName() in {"pageHeading", "titleBar"}:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._drag_offset = (
                        event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    )
                    return True
            elif event.type() == QEvent.Type.MouseMove and self._drag_offset is not None:
                if event.buttons() & Qt.MouseButton.LeftButton and not self.isMaximized():
                    self.move(event.globalPosition().toPoint() - self._drag_offset)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
        return super().eventFilter(watched, event)

    def _choose_color(self, setting_key):
        current_color = self.settings.value(
            setting_key,
            self.accent_color if setting_key == "ui/accent_color" else self.surface_color,
            type=str
        )
        color = QColorDialog.getColor(QColor(current_color), self, "Pilih warna")
        if color.isValid():
            self.settings.setValue(setting_key, color.name())
            if setting_key == "ui/accent_color":
                self.accent_color = color.name()
            else:
                self.surface_color = color.name()
            self.apply_theme()

    def _update_opacity(self, value):
        self.background_opacity = value
        self.opacity_value.setText(f"{value}%")
        self.settings.setValue("ui/background_opacity", value)
        self.apply_theme()

    def _reset_theme(self):
        self.accent_color = "#6C8CFF"
        self.surface_color = "#101827"
        self.background_opacity = 82
        self.settings.setValue("ui/accent_color", self.accent_color)
        self.settings.setValue("ui/surface_color", self.surface_color)
        self.settings.setValue("ui/background_opacity", self.background_opacity)
        self.opacity_slider.setValue(self.background_opacity)
        self.apply_theme()

    def apply_theme(self):
        accent = QColor(self.accent_color)
        surface = QColor(self.surface_color)
        hover = accent.lighter(115).name()
        pressed = accent.darker(115).name()
        alpha = round(self.background_opacity * 255 / 100)
        surface_text = self._contrast_text_color(self.surface_color)
        accent_text = self._contrast_text_color(self.accent_color)
        hover_text = self._contrast_text_color(hover)
        pressed_text = self._contrast_text_color(pressed)
        disabled_text = self._contrast_text_color("#26324A")
        muted_text = "#CBD5E1" if surface_text == "#F8FAFC" else "#475569"
        stylesheet = f"""
QWidget#windowRoot {{ background: transparent; color: {surface_text}; font-family: 'Segoe UI'; }}
QFrame#appSurface {{ background-color: rgba({surface.red()}, {surface.green()}, {surface.blue()}, {alpha}); border: 1px solid rgba(255,255,255,35); border-radius: 20px; }}
QFrame#sidebar {{ background-color: rgba(5,10,20,105); border-top-left-radius: 20px; border-bottom-left-radius: 20px; border-right: 1px solid rgba(255,255,255,22); }}
QFrame#contentArea, QStackedWidget, QWidget {{ background: transparent; color: {surface_text}; font-family: 'Segoe UI'; }}
QLabel#brandLogo {{ color: {accent_text}; background-color: {self.accent_color}; border-radius: 12px; font-size: 19px; font-weight: 800; min-width: 48px; min-height: 48px; }}
QLabel#brandTitle {{ color: #F1F5F9; font-size: 15px; font-weight: 800; letter-spacing: 1px; }}
QLabel#brandSubtitle, QLabel#sidebarFooter {{ color: #8492A8; font-size: 9px; font-weight: 700; letter-spacing: 1.5px; }}
QLabel#pageHeading {{ padding-bottom: 2px; }}
QLabel#subtitle {{ color: {muted_text}; }}
QLabel#fieldLabel {{ color: {muted_text}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
QLabel#cardTitle {{ color: {surface_text}; font-size: 15px; font-weight: 700; }}
QLabel#opacityValue {{ color: {accent_text}; font-weight: 700; }}
QFrame#contentCard {{ background-color: rgba(8,15,28,105); border: 1px solid rgba(255,255,255,28); border-radius: 16px; }}
QProgressBar#downloadProgress {{ background-color: rgba(5,10,20,155); border: 1px solid rgba(255,255,255,36); border-radius: 8px; min-height: 18px; color: #FFFFFF; text-align: center; font-weight: 700; }}
QProgressBar#downloadProgress::chunk {{ background-color: {self.accent_color}; border-radius: 7px; }}
QPushButton#navButton {{ text-align: left; background: transparent; color: #A7B3C7; border: 1px solid transparent; border-radius: 10px; padding: 13px 12px; spacing: 12px; font-size: 12px; font-weight: 600; }}
QPushButton#navButton:hover {{ background-color: rgba(255,255,255,18); color: #FFFFFF; }}
QPushButton#navButton:checked {{ background-color: {self.accent_color}; color: {accent_text}; border: 1px solid rgba({accent.red()}, {accent.green()}, {accent.blue()}, 100); font-weight: 800; }}
QLineEdit, QComboBox, QTextEdit {{ background-color: rgba(5,10,20,155); border: 1px solid rgba(255,255,255,36); border-radius: 10px; padding: 11px 12px; color: #F8FAFC; selection-background-color: {self.accent_color}; selection-color: #FFFFFF; }}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{ border: 1px solid {self.accent_color}; }}
QComboBox QAbstractItemView {{ background-color: #141B2D; color: #F8FAFC; selection-background-color: {self.accent_color}; selection-color: #FFFFFF; border: 1px solid #26324A; outline: 0; }}
QPushButton#downloadButton {{ background-color: {self.accent_color}; border: none; border-radius: 10px; padding: 14px 16px; color: {accent_text}; }}
QPushButton#downloadButton:hover {{ background-color: {hover}; color: {hover_text}; }}
QPushButton#downloadButton:pressed {{ background-color: {pressed}; color: {pressed_text}; }}
QPushButton#downloadButton:disabled {{ background-color: #26324A; color: {disabled_text}; }}
QPushButton#secondaryButton {{ background-color: rgba(255,255,255,15); border: 1px solid rgba(255,255,255,35); border-radius: 9px; padding: 10px 14px; color: {surface_text}; font-size: 10px; font-weight: 700; }}
QPushButton#secondaryButton:hover {{ background-color: rgba(255,255,255,28); }}
QPushButton#windowButton, QPushButton#closeButton {{ background-color: rgba(255,255,255,12); border: 1px solid rgba(255,255,255,25); border-radius: 8px; min-width: 32px; max-width: 32px; min-height: 30px; max-height: 30px; color: {surface_text}; font-size: 16px; }}
QPushButton#windowButton:hover {{ background-color: rgba(255,255,255,32); }}
QPushButton#closeButton:hover {{ background-color: #D94B57; color: #FFFFFF; }}
QPushButton#accentColorButton, QPushButton#surfaceColorButton {{ background-color: #202B3D; border: 1px solid rgba(255,255,255,45); border-radius: 8px; padding: 7px 10px; color: #FFFFFF; font-weight: 700; }}
QTextEdit#logArea {{ background-color: rgba(5,10,20,150); border: 1px solid rgba(255,255,255,35); border-radius: 12px; padding: 12px; }}
QSlider::groove:horizontal {{ height: 6px; background: rgba(255,255,255,40); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {self.accent_color}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: #FFFFFF; border: 2px solid {self.accent_color}; width: 16px; margin: -6px 0; border-radius: 9px; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 4px; }}
QScrollBar::handle:vertical {{ background: rgba(180,195,220,90); border-radius: 4px; min-height: 25px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""
        self.setStyleSheet(stylesheet)
        self._update_maximize_icon()
        self._show_page(self.pages.currentIndex())
        self.opacity_value.setText(f"{self.background_opacity}%")
        for key, name in (
            ("ui/accent_color", "accentColorButton"),
            ("ui/surface_color", "surfaceColorButton"),
        ):
            button = self.findChild(QPushButton, name)
            if button:
                color = self.settings.value(
                    key,
                    self.accent_color if key == "ui/accent_color" else self.surface_color,
                    type=str
                )
                button.setText(color.upper())
                button_text = self._contrast_text_color(color)
                button.setStyleSheet(
                    f"background-color: {color}; color: {button_text}; border: 1px solid "
                    "rgba(255,255,255,90); border-radius: 8px; padding: 7px 10px; "
                    "font-weight: 700;"
                )

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
        self.download_progress.setValue(0)
        self.progress_heading.setText("Menyiapkan unduhan")
        self._apply_download_active(True)

        thread = threading.Thread(target=self._download_thread, args=(url, mode, quality), daemon=True)
        thread.start()

    def post_log(self, message):
        if not message:
            return
        QMetaObject.invokeMethod(self, "_append_log", Qt.ConnectionType.QueuedConnection, Q_ARG(str, message))

    @pyqtSlot(str)
    def _append_log(self, message):
        self._log_lines.append(message)
        self.log_area.setPlainText('\n'.join(self._log_lines))
        self.log_area.moveCursor(QTextCursor.MoveOperation.End)
        self._update_progress_phase(message)
        match = re.search(r'(?<![\d.])(\d{1,3}(?:\.\d+)?)%', message)
        if match:
            percentage = max(0, min(100, round(float(match.group(1)))))
            self.download_progress.setValue(percentage)

    def _update_progress_phase(self, message):
        lowered = message.lower()
        if any(phrase in lowered for phrase in (
            "mulai proses encode", "processing audio with ffmpeg",
            "encoding progres", "encode selesai",
        )):
            self.progress_heading.setText("Encoding")
        elif any(phrase in lowered for phrase in (
            "download audio", "downloading mp3",
        )):
            self.progress_heading.setText("Audio Download")
        elif any(phrase in lowered for phrase in (
            "download video", "mulai mengunduh dari",
        )):
            self.progress_heading.setText("Video Download")

    def _set_download_active(self, active):
        QMetaObject.invokeMethod(
            self, "_apply_download_active", Qt.ConnectionType.QueuedConnection,
            Q_ARG(bool, active)
        )

    @pyqtSlot(bool)
    def _apply_download_active(self, active):
        self.download_btn.setEnabled(not active)
        self.download_progress_card.setVisible(active)

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
            self._set_download_active(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 12))
    ui = DownloaderUI()
    ui.showMaximized()
    sys.exit(app.exec())