"""Theme engine: builds a Qt style sheet from a palette + accent colour.

Three modes — ``light``, ``dark``, ``system`` (resolved against the OS at
apply time). The accent colour is user-selectable from :data:`config.ACCENTS`.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from .. import config


@dataclass(frozen=True)
class Palette:
    bg: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_dim: str
    accent: str
    accent_text: str
    danger: str
    success: str
    hover: str


def _mix(a: str, b: str, t: float) -> str:
    ca, cb = QColor(a), QColor(b)
    return QColor(
        round(ca.red() + (cb.red() - ca.red()) * t),
        round(ca.green() + (cb.green() - ca.green()) * t),
        round(ca.blue() + (cb.blue() - ca.blue()) * t),
    ).name()


def _readable_on(hex_color: str) -> str:
    c = QColor(hex_color)
    luminance = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255
    return "#111111" if luminance > 0.6 else "#ffffff"


def resolve_mode(mode: str) -> str:
    if mode != "system":
        return mode
    hints = QApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    if scheme is not None:
        return "dark" if scheme() == Qt.ColorScheme.Dark else "light"
    win = QApplication.palette().color(QPalette.Window)
    return "dark" if win.lightness() < 128 else "light"


def build_palette(mode: str, accent_name: str) -> Palette:
    accent = config.ACCENTS.get(accent_name, config.ACCENTS["Red"])
    if resolve_mode(mode) == "dark":
        return Palette(
            bg="#16181d",
            surface="#1e2128",
            surface_alt="#252932",
            border="#333844",
            text="#e8eaed",
            text_dim="#9aa0ab",
            accent=accent,
            accent_text=_readable_on(accent),
            danger="#ff5c5c",
            success="#4caf82",
            hover=_mix("#1e2128", "#ffffff", 0.06),
        )
    return Palette(
        bg="#f4f5f7",
        surface="#ffffff",
        surface_alt="#eef0f3",
        border="#d9dce1",
        text="#1c1e21",
        text_dim="#6b7280",
        accent=accent,
        accent_text=_readable_on(accent),
        danger="#d64545",
        success="#2e7d5b",
        hover=_mix("#ffffff", "#000000", 0.04),
    )


def build_stylesheet(p: Palette) -> str:
    accent_hover = _mix(p.accent, "#ffffff", 0.12)
    accent_press = _mix(p.accent, "#000000", 0.12)
    return f"""
* {{
    font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    color: {p.text};
}}
QWidget#Root, QMainWindow, QDialog {{ background: {p.bg}; }}
QToolTip {{
    background: {p.surface}; color: {p.text};
    border: 1px solid {p.border}; padding: 4px 8px; border-radius: 4px;
}}

/* -- navigation rail -- */
QFrame#NavRail {{ background: {p.surface}; border-right: 1px solid {p.border}; }}
QPushButton#NavButton {{
    text-align: left; padding: 10px 16px; border: none; border-radius: 8px;
    color: {p.text_dim}; background: transparent; font-size: 13px;
}}
QPushButton#NavButton:hover {{ background: {p.hover}; color: {p.text}; }}
QPushButton#NavButton:checked {{
    background: {p.accent}; color: {p.accent_text}; font-weight: 600;
}}
QLabel#AppWordmark {{ font-size: 15px; font-weight: 700; color: {p.text}; }}

/* -- cards / panels -- */
QFrame#Card {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: 12px;
}}
QFrame#Inset {{ background: {p.surface_alt}; border-radius: 10px; }}
QLabel#H1 {{ font-size: 22px; font-weight: 700; }}
QLabel#H2 {{ font-size: 15px; font-weight: 600; }}
QLabel#Dim {{ color: {p.text_dim}; }}
QLabel#Pill {{
    background: {_mix(p.surface, p.accent, 0.16)}; color: {p.text};
    border: 1px solid {_mix(p.border, p.accent, 0.4)};
    border-radius: 10px; padding: 3px 11px; font-size: 11px; font-weight: 600;
}}
QLabel#SectionLabel {{
    color: {p.text_dim}; font-size: 10px; font-weight: 700; letter-spacing: 1px;
}}
QLabel#MetaLine {{ color: {p.accent}; font-size: 12px; font-weight: 600; }}
QFrame#Banner {{
    background: {_mix(p.surface, p.danger, 0.14)};
    border: 1px solid {_mix(p.border, p.danger, 0.5)}; border-radius: 10px;
}}
QFrame#Banner QLabel {{ color: {p.text}; }}

/* -- inputs -- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 8px; padding: 8px 10px; selection-background-color: {p.accent};
    selection-color: {p.accent_text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {p.accent}; }}
QLineEdit#Search {{ font-size: 15px; padding: 12px 14px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; border: 1px solid {p.border};
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
    outline: 0;
}}

/* -- buttons -- */
QPushButton {{
    background: {p.surface_alt}; border: 1px solid {p.border};
    border-radius: 8px; padding: 8px 16px; color: {p.text};
}}
QPushButton:hover {{ background: {p.hover}; }}
QPushButton:disabled {{ color: {p.text_dim}; background: {p.surface}; }}
QPushButton#Primary {{
    background: {p.accent}; color: {p.accent_text}; border: none; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {accent_hover}; }}
QPushButton#Primary:pressed {{ background: {accent_press}; }}
QPushButton#Ghost {{ background: transparent; border: none; color: {p.text_dim}; }}
QPushButton#Ghost:hover {{ color: {p.text}; background: {p.hover}; }}
QPushButton#Danger {{ color: {p.danger}; border-color: {p.border}; background: transparent; }}
QPushButton#Danger:hover {{ background: {_mix(p.surface, p.danger, 0.12)}; }}

/* -- checkboxes / radios -- */
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox::indicator {{ border: 1px solid {p.border}; border-radius: 4px; background: {p.surface_alt}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
QRadioButton::indicator {{ border: 1px solid {p.border}; border-radius: 8px; background: {p.surface_alt}; }}
QRadioButton::indicator:checked {{ background: {p.accent}; border: 4px solid {p.accent}; }}

/* -- progress -- */
QProgressBar {{
    background: {p.surface_alt}; border: none; border-radius: 6px;
    height: 8px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 6px; }}

/* -- tabs -- */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; padding: 8px 14px; color: {p.text_dim};
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {p.text}; border-bottom: 2px solid {p.accent}; }}

/* -- scrollbars -- */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QAbstractScrollArea {{ background: transparent; }}
QListWidget {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: 8px;
    padding: 4px;
}}
QListWidget::item {{ padding: 5px 6px; border-radius: 5px; }}
QListWidget::item:hover {{ background: {p.hover}; }}
QTabWidget > QWidget {{ background: transparent; }}
QTabWidget::pane {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_dim}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 30px; }}

/* -- queue rows -- */
QFrame#QueueRow {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: 10px; }}
QFrame#QueueRow[state="completed"] {{ border-left: 3px solid {p.success}; }}
QFrame#QueueRow[state="failed"] {{ border-left: 3px solid {p.danger}; }}
QFrame#QueueRow[state="running"] {{ border-left: 3px solid {p.accent}; }}

QLabel#Toast {{
    background: {p.text}; color: {p.bg}; border-radius: 8px; padding: 10px 16px;
}}
"""


def apply_theme(app: QApplication, mode: str, accent_name: str) -> Palette:
    palette = build_palette(mode, accent_name)
    app.setStyleSheet(build_stylesheet(palette))
    app.setProperty("ytpdl_palette", palette)
    return palette
