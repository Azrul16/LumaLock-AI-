"""Dark palette with clear hierarchy and accessible control contrast."""

STYLE = """
QMainWindow, QDialog { background: #11151b; color: #e5eaf1; }
QWidget { color: #e5eaf1; font-family: 'Segoe UI'; font-size: 12px; }
QLabel#sectionTitle { font-size: 19px; font-weight: 600; color: #eef9f7; padding: 5px 0; }
QPushButton#look { background: #223330; border: 1px solid #36514b; padding: 11px; text-align: left; }
QPushButton#look:hover { background: #304d44; border-color: #6bd1b2; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #536173; border-radius: 3px; background: #151d26; }
QCheckBox::indicator:checked { background: #4bb697; border-color: #76d8bc; }
QScrollBar:vertical { background: #18202a; width: 8px; }
QScrollBar::handle:vertical { background: #46566b; min-height: 24px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QFrame#panel { background: #191f28; border: 1px solid #29313d; border-radius: 8px; }
QLabel#brand { font-size: 22px; font-weight: 700; color: #fafcff; }
QLabel#muted { color: #9ca9ba; }
QPushButton { background: #293342; border: 1px solid #39485b; border-radius: 5px; padding: 7px 12px; }
QPushButton:hover { background: #384960; }
QPushButton:disabled { color: #667386; background: #202731; }
QPushButton#primary { background: #377de5; border-color: #528fee; font-weight: 600; }
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #111820; border: 1px solid #344153; border-radius: 4px; padding: 5px; selection-background-color: #377de5; }
QListWidget { background: #121923; border: 1px solid #2c3746; border-radius: 4px; }
QListWidget::item { padding: 7px; }
QListWidget::item:selected { background: #284d7c; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #1b2532; padding: 8px; color: #a9b7c9; }
QTabBar::tab:selected { background: #2e4564; color: white; }
QSlider::groove:horizontal { height: 4px; background: #364355; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4e90ee; }
QSlider::handle:horizontal { background: #b8d4ff; width: 10px; margin: -4px 0; border-radius: 5px; }
QProgressBar { border: 0; background: #222c3a; border-radius: 3px; text-align: center; }
QProgressBar::chunk { background: #377de5; }
QMenuBar, QMenu { background: #1b222e; color: #e5eaf1; }
QScrollArea { border: 0; background: transparent; }
QToolTip { background: #26364b; color: white; border: 1px solid #4e6381; }
"""
