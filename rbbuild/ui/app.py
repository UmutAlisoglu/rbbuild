# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import tomllib
from collections import deque
from importlib import resources
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import (
    QAction, QColor, QIcon, QKeySequence, QPixmap, QTextCharFormat,
    QTextCursor)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)

from rbbuild.container.application import Application
from rbbuild.ui import console_capture
from rbbuild.ui.config.view import ConfigEditorView
from rbbuild.version import RBBuildVersion, __version__


# Delivers console messages captured on arbitrary background threads onto
# the Qt main thread - signal emission is thread-safe, and Qt auto-queues
# delivery to a receiver living on a different thread than the emitter.
class _ConsoleBridge(QObject):
    message_received = Signal(str, str)


# Shared shell for all rbbuild GUI tools. Owns the QMainWindow, the
# dependency-injection container, and common chrome (icon, spacer banner,
# busy cursor, tab switcher, Active Deps sidebar). A tool-specific content
# widget is mounted via set_content(). See
# documentation/developer-manual/gui_architecture.md.
class RBBuildGuiApp(QMainWindow):

    MAX_MESSAGES = 4000  # max captured console lines kept in memory/shown in the messages panel

    def __init__(self, application: Application, title: str, qt_app: QApplication):
        super().__init__()
        self.application = application
        self.qt_app = qt_app
        self.content: Optional[QWidget] = None
        self.base_title = title

        self.setWindowTitle(title)
        self.resize(1600, 1200)

        central = QWidget(self)
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setContentsMargins(12, 12, 12, 12)

        self._load_icon()
        self._create_spacer()
        self._create_workspace()
        self._create_console_panel()
        self._install_console_capture()
        self._create_menu_bar()


    # Tab switcher (left, tool views) plus a sidebar (right) that stays
    # visible regardless of the active tab.
    def _create_workspace(self):
        self.active_deps: list = []

        self.frame_workspace = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.frame_workspace, 1)

        self.notebook = QTabWidget()
        self.frame_workspace.addWidget(self.notebook)

        self.tab_config_editor = ConfigEditorView(
            self.notebook, self.active_deps,
            on_active_deps_change=self.refresh_active_deps,
            on_loaded_path_change=self._update_title,
            deps_parser=self.application.deps.parser(),
            on_jump_to_pkq=self._switch_to_package_query)
        self.notebook.addTab(self.tab_config_editor, 'Workspace Editor')

        self.frame_sidebar = QWidget()
        self.frame_workspace.addWidget(self.frame_sidebar)
        self.frame_workspace.setStretchFactor(0, 3)
        self.frame_workspace.setStretchFactor(1, 1)
        self._create_active_deps_sidebar()

        self.notebook.currentChanged.connect(self._update_sidebar_visibility)
        self.tab_config_editor.sub_notebook.currentChanged.connect(self._update_sidebar_visibility)


    # The dependencies sub-tab already shows the same entries in its own
    # list, so the sidebar is hidden while it's the active (sub-)tab to
    # avoid showing a duplicate.
    def _update_sidebar_visibility(self):
        on_editor_tab = self.notebook.currentWidget() is self.tab_config_editor
        on_deps_subtab = (
            on_editor_tab
            and self.tab_config_editor.sub_notebook.currentWidget() is self.tab_config_editor.deps_view)
        self.frame_sidebar.setVisible(not on_deps_subtab)


    # Global File/Help menu bar. Every entry stays enabled regardless of the
    # active tab - File actions switch to the Workspace Editor tab first.
    def _create_menu_bar(self):
        menubar = self.menuBar()

        menu_file = menubar.addMenu('&File')
        menu_new = menu_file.addMenu('New Workspace')

        act_new_rbbuild = QAction('rbbuild.toml', self)
        act_new_rbbuild.setShortcut(QKeySequence('Ctrl+N'))
        act_new_rbbuild.triggered.connect(lambda: self._menu_new('rbbuild.toml'))
        menu_new.addAction(act_new_rbbuild)

        act_new_pyproject = QAction('pyproject.toml', self)
        act_new_pyproject.triggered.connect(lambda: self._menu_new('pyproject.toml'))
        menu_new.addAction(act_new_pyproject)

        act_open = QAction('Open Workspace...', self)
        act_open.setShortcut(QKeySequence('Ctrl+O'))
        act_open.triggered.connect(self._menu_open)
        menu_file.addAction(act_open)

        act_save = QAction('Save Workspace', self)
        act_save.setShortcut(QKeySequence('Ctrl+S'))
        act_save.triggered.connect(self._menu_save)
        menu_file.addAction(act_save)

        menu_save_as = menu_file.addMenu('Save As')

        act_save_as_rbbuild = QAction('rbbuild.toml', self)
        act_save_as_rbbuild.triggered.connect(lambda: self._menu_save_as('rbbuild.toml'))
        menu_save_as.addAction(act_save_as_rbbuild)

        act_save_as_pyproject = QAction('pyproject.toml', self)
        act_save_as_pyproject.triggered.connect(lambda: self._menu_save_as('pyproject.toml'))
        menu_save_as.addAction(act_save_as_pyproject)

        menu_help = menubar.addMenu('&Help')
        act_about = QAction('About', self)
        act_about.triggered.connect(self._menu_about)
        menu_help.addAction(act_about)


    def _switch_to_workspace_editor(self):
        self.notebook.setCurrentWidget(self.tab_config_editor)


    def _switch_to_package_query(self):
        if self.content is not None:
            self.notebook.setCurrentWidget(self.content)


    def _menu_new(self, target_format: str):
        self._switch_to_workspace_editor()
        self.tab_config_editor.trigger_new(target_format)


    def _menu_open(self):
        self._switch_to_workspace_editor()
        self.tab_config_editor.trigger_open()


    def _menu_save(self):
        self._switch_to_workspace_editor()
        self.tab_config_editor.trigger_save()


    def _menu_save_as(self, target_format: str):
        self._switch_to_workspace_editor()
        self.tab_config_editor.trigger_save_as(target_format)


    def _menu_about(self):
        text = (
            f'rbbuild Command Center {__version__}\n\n'
            'Authors:\n' + '\n'.join(f'  {a}' for a in self._load_authors()) +
            '\n\nLicense: Bosch InnerSource License (BISL) 1.0 (see bisl-1.0.txt)')
        QMessageBox.information(self, 'About rbbuild Command Center', text)


    def _load_authors(self) -> list:
        pyproject_toml_path = RBBuildVersion().root_path / 'pyproject.toml'
        try:
            with open(pyproject_toml_path, 'rb') as fd:
                data = tomllib.load(fd)
            return [author['name'] for author in data['project'].get('authors', [])]
        except (OSError, KeyError):
            return []


    # Reflects the loaded workspace's folder in the title bar - wired as
    # ConfigEditorView's on_loaded_path_change callback.
    def _update_title(self, loaded_path: Optional[Path]):
        if loaded_path:
            self.setWindowTitle(f'{self.base_title}: {Path(loaded_path).parent}')
        else:
            self.setWindowTitle(self.base_title)


    def _create_active_deps_sidebar(self):
        layout = QVBoxLayout(self.frame_sidebar)
        layout.addWidget(QLabel('Active Deps'))

        self.tree_active_deps = QTreeWidget()
        self.tree_active_deps.setHeaderLabels(['Entry'])
        self.tree_active_deps.setSelectionMode(QTreeWidget.SingleSelection)
        layout.addWidget(self.tree_active_deps, 1)

        btn_remove = QPushButton('Remove')
        btn_remove.clicked.connect(self._on_remove_active_dep)
        layout.addWidget(btn_remove, 0, Qt.AlignRight)


    # Removes the selected sidebar entry from the shared active_deps list.
    def _on_remove_active_dep(self):
        selected = self.tree_active_deps.selectedItems()
        if not selected:
            return
        index = self.tree_active_deps.indexOfTopLevelItem(selected[0])
        del self.active_deps[index]
        self.refresh_active_deps()


    # Repopulates the sidebar tree from self.active_deps (a list of Package
    # objects or plain deps-entry strings/dicts) - called whenever the
    # shared document changes (e.g. "Add to deps list"/drag-and-drop from
    # the Package Query tab).
    def refresh_active_deps(self):
        self.tree_active_deps.clear()
        for item in self.active_deps:
            self.tree_active_deps.addTopLevelItem(QTreeWidgetItem([str(item)]))
        self.tab_config_editor.refresh_active_deps()


    def _load_icon(self):
        icon_file = resources.files('rbbuild').joinpath(
            'resources', 'buildcore-logo.png')
        with resources.as_file(icon_file) as path:
            self.setWindowIcon(QIcon(str(path)))


    def _create_spacer(self):
        spacer_file = resources.files('rbbuild').joinpath('resources', 'rainbow-spacer.png')
        with resources.as_file(spacer_file) as path:
            pixmap = QPixmap(str(path))
        pixmap = pixmap.scaled(
            pixmap.width(), pixmap.height() // 2,
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

        self.lbl_spacer = QLabel()
        self.lbl_spacer.setPixmap(pixmap)
        self.lbl_spacer.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.lbl_spacer)


    # Toggle button + (initially hidden) scrolled text area mirroring all
    # captured console output - see _install_console_capture().
    def _create_console_panel(self):
        self._console_messages = deque(maxlen=self.MAX_MESSAGES)
        self._console_visible = False
        self._unread_count = 0
        self._channel_vars = {}
        self._console_colors = {
            'error': '#a30000',
            'warning': '#8a6d00',
            'info': '#202020',
            'debug': '#808080',
        }

        self.frame_console = QWidget()
        console_layout = QVBoxLayout(self.frame_console)
        console_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.frame_console)

        self.frame_console_bar = QWidget()
        bar_layout = QHBoxLayout(self.frame_console_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.addWidget(self.frame_console_bar)

        self.btn_console = QPushButton('Messages')
        self.btn_console.clicked.connect(self.toggle_console)
        bar_layout.addWidget(self.btn_console)

        for channel in console_capture.CHANNELS:
            chk = QCheckBox(channel.capitalize())
            chk.setChecked(channel != 'debug')
            chk.stateChanged.connect(lambda _state: self._render_console())
            bar_layout.addWidget(chk)
            self._channel_vars[channel] = chk

        bar_layout.addStretch(1)

        self.txt_console = QPlainTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setFixedHeight(160)
        self.txt_console.setVisible(False)
        console_layout.addWidget(self.txt_console)


    # Mirrors every line printed anywhere in the process (sys.stdout/stderr,
    # term.out_file/log_file) into the messages panel above.
    def _install_console_capture(self):
        self._console_bridge = _ConsoleBridge()
        self._console_bridge.message_received.connect(self._add_console_message)
        console_capture.install(self._on_console_message)


    # May be called from a background thread - hands off to the Qt main thread.
    def _on_console_message(self, severity: str, text: str):
        self._console_bridge.message_received.emit(severity, text)


    def _add_console_message(self, severity: str, text: str):
        self._console_messages.append((severity, text))
        if self._console_visible:
            if self._channel_vars[severity].isChecked():
                self._append_console_line(severity, text)
        else:
            self._unread_count += 1
            self.btn_console.setText(f'Messages ({self._unread_count})')


    def _append_console_line(self, severity: str, text: str):
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self._console_colors[severity]))
        cursor = self.txt_console.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.setCharFormat(fmt)
        cursor.insertText(text + '\n')
        self.txt_console.setTextCursor(cursor)
        self.txt_console.ensureCursorVisible()


    # Rebuilds the text area from the full message history, applying the current filter checkboxes.
    def _render_console(self):
        if not self._console_visible:
            return
        self.txt_console.clear()
        for severity, text in self._console_messages:
            if self._channel_vars[severity].isChecked():
                self._append_console_line(severity, text)


    def toggle_console(self):
        if self._console_visible:
            self.txt_console.setVisible(False)
            self._console_visible = False
            return

        self._console_visible = True
        self._render_console()
        self.txt_console.setVisible(True)
        self._unread_count = 0
        self.btn_console.setText('Messages')


    def set_content(self, content: QWidget):
        if self.content is not None:
            index = self.notebook.indexOf(self.content)
            self.notebook.removeTab(index)
            self.content.deleteLater()
        self.notebook.insertTab(0, content, 'Package Query')
        self.content = content
        self.notebook.setCurrentWidget(content)


    def status_busy(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents()


    def status_ready(self):
        QApplication.restoreOverrideCursor()
        QApplication.processEvents()


    def mainloop(self):
        self.show()
        self.qt_app.exec()

