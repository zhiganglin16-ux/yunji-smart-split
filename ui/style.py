# -*- coding: utf-8 -*-
"""云极智能拆版 · 暗黑科技风 QSS 主题"""

DARK_QSS = """
* { font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif; }
QMainWindow, QDialog { background: #0d131b; }
QWidget { color: #e9eef6; font-size: 13px; }

/* ---------- 顶栏 ---------- */
#titleBar { background: #111925; border-bottom: 1px solid #26334a; }
#titleBar QLabel { font-size: 15px; font-weight: 800; color: #3b82f6; letter-spacing: 1px; }
#titleBar QLabel#subTitle { font-size: 11px; font-weight: 400; color: #7889a3; letter-spacing: 2px; }

QPushButton {
    background: #1c2839; color: #d4deec; border: 1px solid #2c3c55;
    border-radius: 6px; padding: 7px 14px; font-size: 13px;
}
QPushButton:hover { background: #26344b; border-color: #3d5271; }
QPushButton:pressed { background: #17202f; }
QPushButton#primaryBtn {
    background: #2563eb; color: #fff; border: 1px solid #3b82f6; font-weight: 700;
}
QPushButton#primaryBtn:hover { background: #3b82f6; }
QPushButton#primaryBtn:disabled { background: #1e3a5f; color: #7d8ca3; border-color: #2c4a6e; }
QPushButton#dangerBtn { background: #7f1d1d; border-color: #b91c1c; }
QPushButton#dangerBtn:hover { background: #991b1b; }
QPushButton#ghostBtn { background: transparent; border: 1px dashed #2c3c55; }
QPushButton#ghostBtn:hover { border-color: #3b82f6; color: #3b82f6; }

/* ---------- 面板 ---------- */
QFrame#panel {
    background: #141d2a; border: 1px solid #26334a; border-radius: 10px;
}
QFrame#panel QLabel#panelTitle {
    color: #9db0c8; font-size: 12px; font-weight: 700; letter-spacing: 2px;
}
QGroupBox {
    background: #141d2a; border: 1px solid #26334a; border-radius: 8px;
    margin-top: 12px; padding-top: 6px; font-weight: 700; color: #9db0c8;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }

QLabel { color: #c6d2e2; }
QLabel#mut { color: #7889a3; font-size: 11px; }
QLabel#ok { color: #16a34a; font-weight: 700; }
QLabel#warn { color: #f59e0b; font-weight: 700; }
QLabel#err { color: #ef4444; font-weight: 700; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background: #0f1622; border: 1px solid #2c3c55; border-radius: 5px;
    padding: 5px 8px; color: #e9eef6; selection-background-color: #2563eb;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #3b82f6;
}
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background: #141d2a; border: 1px solid #2c3c55; selection-background-color: #2563eb;
}

QCheckBox { spacing: 7px; color: #c6d2e2; }
QCheckBox::indicator { width: 15px; height: 15px; border-radius: 4px;
    border: 1px solid #3d5271; background: #0f1622; }
QCheckBox::indicator:checked { background: #2563eb; border-color: #3b82f6; }

/* ---------- 页签 ---------- */
QTabWidget::pane { border: 1px solid #26334a; border-radius: 8px; background: #0f141b; top: -1px; }
QTabBar::tab {
    background: #141d2a; color: #9db0c8; padding: 8px 22px; margin-right: 3px;
    border: 1px solid #26334a; border-bottom: none; border-top-left-radius: 7px;
    border-top-right-radius: 7px;
}
QTabBar::tab:selected { background: #0f141b; color: #3b82f6; font-weight: 700; }

/* ---------- 日志 ---------- */
QTextEdit#log {
    background: #0b1017; color: #9db0c8; border: 1px solid #26334a;
    border-radius: 8px; font-family: Consolas, "Courier New", monospace; font-size: 12px;
}

QScrollBar:vertical { background: transparent; width: 9px; }
QScrollBar::handle:vertical { background: #2c3c55; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #3d5271; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 9px; }
QScrollBar::handle:horizontal { background: #2c3c55; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QProgressBar {
    background: #0f1622; border: 1px solid #2c3c55; border-radius: 6px;
    text-align: center; color: #e9eef6; height: 18px;
}
QProgressBar::chunk { background: #2563eb; border-radius: 5px; }

QStatusBar { background: #111925; color: #7889a3; border-top: 1px solid #26334a; }
QMenu { background: #141d2a; border: 1px solid #2c3c55; }
QMenu::item:selected { background: #2563eb; }
QToolTip { background: #141d2a; color: #e9eef6; border: 1px solid #3b82f6; }
"""
