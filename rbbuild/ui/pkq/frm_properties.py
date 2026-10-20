# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import datetime
import shutil
import webbrowser
from importlib import resources
from pathlib import Path
from typing import Callable, Optional, TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QMenu, QPushButton, QTextEdit,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from rbbuild.librbb.term import term
from rbbuild.ui.async_task import AsyncTaskQueue
from rbbuild.ui.pkq.control import PkqController

if TYPE_CHECKING:
    from rbbuild.ui.pkq.view import PkqView


# Properties panel: package metadata (top) + components tree (bottom).
class PkqPropertiesFrame:

    def __init__(self, parent: 'PkqView', master: QWidget, controller: PkqController):
        self.master = master
        self.parent = parent
        self.controller = controller
        self.icon_package_file = self._load_icon()
        self._component_names = {}  # QTreeWidgetItem -> full component filename
        self._frm = self._create_frm(master)
        self._download_queue = AsyncTaskQueue(self.master)
        self.update_all()


    @property
    def frm(self) -> QWidget:
        return self._frm


    def _load_icon(self) -> QIcon:
        icon_file = resources.files('rbbuild').joinpath('resources', 'package_file_16.png')
        with resources.as_file(icon_file) as path:
            return QIcon(str(path))


    def _create_frm(self, master: QWidget) -> QWidget:
        frm = QWidget(master)
        layout = QVBoxLayout(frm)
        layout.setContentsMargins(4, 0, 0, 0)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setContextMenuPolicy(Qt.CustomContextMenu)
        self.text.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.text, 1)

        hide_row = QHBoxLayout()
        hide_row.addStretch(1)
        self.btn_hide = QPushButton('Hide')
        self.btn_hide.clicked.connect(self.hide)
        hide_row.addWidget(self.btn_hide)
        layout.addLayout(hide_row)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(1)
        self.tree.setHeaderLabels(['Components'])
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_components_menu)
        layout.addWidget(self.tree, 1)

        self._create_context_menu()
        self._create_components_menu()

        return frm


    def show(self):
        self.frm.setVisible(True)


    def hide(self):
        self.frm.setVisible(False)


    def clear_all(self):
        self.clear_text()
        self.clear_components()


    def clear_text(self):
        self.text.clear()


    def clear_components(self):
        self.tree.clear()
        self._component_names = {}


    def update_all(self):
        self.update_text()
        self.update_components()


    # From version.py: our base date. Computed with the following command:
    #   echo "$(date --date='2018-04-16' +%s) / ((60*60*24))" | bc
    def _date_from_version_string(self, version: str) -> str:
        date_2018_04_16 = 17636
        revision = version.split('.')[2].split('-')[0]
        date_epoch = int(revision) + date_2018_04_16
        return datetime.datetime.fromtimestamp(date_epoch * 60 * 60 * 24).strftime('%a %d %b %Y')


    def update_text(self):
        self.clear_text()
        pkg = self.controller.package
        if not pkg:
            return

        self._insert(str(pkg) + '\n\n', bold=True, size=13)

        if pkg.version:
            self._insert('Date:\n', bold=True, size=12)
            try:
                date = self._date_from_version_string(pkg.version)
            except Exception:
                date = 'Unknown'
            self._insert(date + '\n\n')

        if pkg.branch:
            self._insert('Branch:\n', bold=True, size=12)
            self._insert(pkg.branch + '\n\n')

        if pkg.toolchain:
            self._insert('Toolchain:\n', bold=True, size=12)
            self._insert(str(pkg.toolchain) + '\n\n')

        if pkg.git_repo:
            self._insert('Git Repository:\n', bold=True, size=12)
            self._insert(pkg.git_repo + '\n\n')

        if pkg.git_hash:
            self._insert('Git Commit:\n', bold=True, size=12)
            self._insert(pkg.git_hash + '\n\n')

        if pkg.channel:
            self._insert('Channel:\n', bold=True, size=12)
            self._insert(pkg.channel.name + '\n\n')

        if pkg.url:
            self._insert('Url:\n', bold=True, size=12)
            self._insert(pkg.url + '\n\n')


    def _insert(self, text: str, bold: bool = False, size: int = 10):
        font = QFont('Arial', size)
        font.setBold(bold)
        fmt = QTextCharFormat()
        fmt.setFont(font)

        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.text.setTextCursor(cursor)


    def update_components(self):
        self.clear_components()
        pkg = self.controller.package
        if not pkg or not pkg.components:
            return

        # Package.components is a flat list; group by name for display.
        groups = {}
        for component in pkg.components:
            groups.setdefault(component.name, []).append(component)

        for name, components in groups.items():
            group_item = QTreeWidgetItem([name])
            self.tree.addTopLevelItem(group_item)
            group_item.setExpanded(True)
            for component in components:
                if component.filename:
                    squeezed = self._squeeze(component.filename)
                    leaf_item = QTreeWidgetItem([squeezed])
                    leaf_item.setIcon(0, self.icon_package_file)
                    group_item.addChild(leaf_item)
                    self._component_names[leaf_item] = component.filename
                    if squeezed != component.filename:
                        leaf_item.setToolTip(0, component.filename)


    @staticmethod
    def _squeeze(name: str, max_len: int = 60) -> str:
        if len(name) <= max_len:
            return name

        keep_start = max_len // 3
        keep_end = max_len - keep_start - 1
        return name[:keep_start] + '\u2026' + name[-keep_end:]


    def _create_context_menu(self):
        self._text_menu = QMenu(self.text)
        self._text_menu.addAction('Copy', self.copy_selected_text)
        self._text_menu.addAction('Copy all', self.copy_all_text)


    def show_context_menu(self, pos):
        self._text_menu.exec(self.text.viewport().mapToGlobal(pos))


    def copy_selected_text(self):
        self.text.copy()


    def copy_all_text(self):
        QApplication.clipboard().setText(self.text.toPlainText())


    def _create_components_menu(self):
        self._components_menu = QMenu(self.tree)
        self._components_menu.addAction('Download to ...', self.download_selected_component_to)
        self._components_menu.addAction('Download (cache only)', self.download_selected_component)
        self._components_menu.addSeparator()
        self._act_download_browser = self._components_menu.addAction('Download with browser', self.download_with_browser)
        self._components_menu.addSeparator()
        self._components_menu.addAction('Copy name', self.copy_component_name)
        self._act_copy_link = self._components_menu.addAction('Copy download link', self.copy_component_download_link)


    def show_components_menu(self, pos):
        if not self.tree.currentItem():
            return
        if not self.controller.package:
            return
        if not self.selected_component_is_downloadable:
            return

        # "Download with browser" and "Copy download link" need pkg.url,
        # which not every repository provides - disable just those, not
        # the whole menu.
        has_url = bool(self.controller.package.url)
        self._act_download_browser.setEnabled(has_url)
        self._act_copy_link.setEnabled(has_url)

        self._components_menu.exec(self.tree.viewport().mapToGlobal(pos))


    # Downloads (or fetches from cache) the selected component on a
    # background thread; on_done, if given, is called with the local file
    # path (or None on failure).
    def download_selected_component(self, on_done: Optional[Callable[[Optional[str]], None]] = None):
        component_name = self.selected_component_string
        term.debug(f'Downloading component: {component_name}')

        self.parent.status_busy(f'Downloading {component_name} ...')
        self.parent.show_progress()

        def work(report_progress):
            def progress_cb(ncur, total_len):
                report_progress((ncur, total_len))
            return self.controller.download_package(component_name, progress_cb=progress_cb)

        def on_progress(payload):
            ncur, total_len = payload
            if total_len:
                pct = int(ncur * 100 / total_len)
                self.parent.status_busy(f'Downloading {component_name} ... {pct}%')
                self.parent.set_progress(pct)
            else:
                self.parent.status_busy(f'Downloading {component_name} ...')

        def on_success(file_path):
            self.parent.hide_progress()
            self.parent.status_ready()
            if on_done:
                on_done(file_path)

        def on_error(exc):
            self.parent.hide_progress()
            self.parent.status_ready()
            term.error('failed', exc)
            if on_done:
                on_done(None)

        self._download_queue.submit(work, on_success, on_error, on_progress)


    def download_selected_component_to(self):
        default_dir = Path.home() / 'Downloads'
        last_dir = self.controller.history.last_download_dir
        initial_dir = Path(last_dir) if last_dir and Path(last_dir).is_dir() else default_dir
        fname, _selected_filter = QFileDialog.getSaveFileName(
            self.master, 'Download to', str(initial_dir / self.selected_component_string))
        if not fname:
            return

        fname = Path(fname)
        self.controller.history.last_download_dir = str(fname.parent)

        component_name = self.selected_component_string

        def on_done(fname_source):
            if not fname_source:
                term.error('failed', f'Could not download {component_name}')
                return

            fname_source = Path(fname_source)
            term.debug(f'Copying package component from: {fname_source}')
            term.debug(f'Destination: {fname}')

            term.info(f'[{term.green("*")}] {fname_source.name} (copy)')
            shutil.copy(fname_source, fname)

        self.download_selected_component(on_done=on_done)


    def download_with_browser(self):
        url = self.selected_component_url
        term.info(f'Downloading URL: {url}')
        webbrowser.open(url)


    def copy_component_name(self):
        QApplication.clipboard().setText(self.selected_component_string)


    def copy_component_download_link(self):
        QApplication.clipboard().setText(self.selected_component_url)


    @property
    def selected_component_string(self) -> str:
        item = self.tree.currentItem()
        return self._component_names.get(item, item.text(0))


    @property
    def selected_component_url(self) -> str:
        return self.controller.package.url + '/' + self.selected_component_string


    @property
    def selected_component_is_downloadable(self) -> bool:
        return '.' in self.selected_component_string
