# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from importlib import resources
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QComboBox, QHBoxLayout, QMenu, QPushButton, QWidget

from rbbuild.ui.pkq.control import PkqController

if TYPE_CHECKING:
    from rbbuild.ui.pkq.view import PkqView


# QComboBox that repopulates its item list right before the dropdown opens.
class _HistoryComboBox(QComboBox):

    def __init__(self, on_about_to_show, parent=None):
        super().__init__(parent)
        self._on_about_to_show = on_about_to_show


    def showPopup(self):
        self._on_about_to_show()
        super().showPopup()


# Query bar: back/forward/home navigation + package text entry + Search button
# + profile combobox + toolchain combobox.
class PkqQueryFrame:

    def __init__(self, parent: 'PkqView', master: QWidget, controller: PkqController):
        self.master = master
        self.parent = parent
        self.controller = controller
        self.icon_home = self._load_icon()
        self._frm = self._create_frm(master)
        self._create_query_context_menu()
        self.update_profiles()
        self.update_channels()
        self.update_toolchains()


    @property
    def frm(self) -> QWidget:
        return self._frm


    def _load_icon(self) -> QIcon:
        icon_file = resources.files('rbbuild').joinpath('resources', 'home_icon_16x16.png')
        with resources.as_file(icon_file) as path:
            return QIcon(str(path))


    def _create_frm(self, master: QWidget) -> QWidget:
        frm_query = QWidget(master)
        layout = QHBoxLayout(frm_query)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_back = QPushButton('<')
        self.btn_back.setFixedWidth(30)
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.parent.go_back)
        layout.addWidget(self.btn_back)

        self.btn_forward = QPushButton('>')
        self.btn_forward.setFixedWidth(30)
        self.btn_forward.setEnabled(False)
        self.btn_forward.clicked.connect(self.parent.go_forward)
        layout.addWidget(self.btn_forward)

        self.btn_home = QPushButton()
        self.btn_home.setIcon(self.icon_home)
        self.btn_home.clicked.connect(self.parent.go_home)
        layout.addWidget(self.btn_home)

        self.ent_query = _HistoryComboBox(self.update_history)
        self.ent_query.setEditable(True)
        self.ent_query.lineEdit().returnPressed.connect(self.parent.query)
        self.ent_query.textActivated.connect(self.select_history)
        self.ent_query.lineEdit().setContextMenuPolicy(Qt.CustomContextMenu)
        self.ent_query.lineEdit().customContextMenuRequested.connect(self.show_query_context_menu)
        layout.addWidget(self.ent_query, 1)

        self.btn_query = QPushButton('Search')
        self.btn_query.clicked.connect(self.parent.query)
        layout.addWidget(self.btn_query)

        self.cmb_profile = QComboBox()
        self.cmb_profile.setFixedWidth(150)
        self.cmb_profile.textActivated.connect(self.select_profile)
        layout.addWidget(self.cmb_profile)

        self.cmb_ch = QComboBox()
        self.cmb_ch.setFixedWidth(220)
        self.cmb_ch.textActivated.connect(self.select_channel)
        layout.addWidget(self.cmb_ch)

        self.cmb_tc = QComboBox()
        self.cmb_tc.setFixedWidth(220)
        self.cmb_tc.textActivated.connect(self.select_toolchain)
        layout.addWidget(self.cmb_tc)

        return frm_query


    def _create_query_context_menu(self):
        self._query_menu = QMenu(self.ent_query)
        self._query_menu.addAction('Copy', self.query_copy_selected_text)
        self._query_menu.addAction('Copy all', self.query_copy_all_text)
        self._query_menu.addAction('Paste', self.query_paste_text)


    @property
    def txt(self) -> str:
        return self.ent_query.currentText()


    @txt.setter
    def txt(self, txt: str):
        self.ent_query.setEditText(txt)


    # Enables/disables the '<' back button (see PkqView.navigate_to_package/go_back).
    def set_back_enabled(self, enabled: bool):
        self.btn_back.setEnabled(enabled)


    # Enables/disables the '>' forward button (see PkqView.go_back/go_forward).
    def set_forward_enabled(self, enabled: bool):
        self.btn_forward.setEnabled(enabled)


    # Populates the profile combobox and selects the currently loaded profile.
    def update_profiles(self):
        profiles = self.controller.profiles
        self.cmb_profile.clear()
        self.cmb_profile.addItems(profiles)
        current = self.controller.profile
        if current in profiles:
            self.cmb_profile.setCurrentIndex(profiles.index(current))


    # A profile switch fully rebuilds the Application and remounts a fresh
    # PkqView/PkqQueryFrame (destroying this one), which populates its own
    # channel combobox - update_channels() here would touch a destroyed widget.
    def select_profile(self, text: str):
        self.parent.change_profile(text)


    def update_channels(self):
        chs = self.controller.channels
        self.cmb_ch.clear()
        self.cmb_ch.addItems(chs)
        current = self.controller.channel
        if str(current) in chs:
            self.cmb_ch.setCurrentIndex(chs.index(str(current)))


    def update_toolchains(self):
        tcs = self.controller.toolchains
        self.cmb_tc.clear()
        self.cmb_tc.addItems(tcs)
        current = self.controller.toolchain
        if str(current) in tcs:
            self.cmb_tc.setCurrentIndex(tcs.index(str(current)))


    def select_channel(self, text: str):
        self.controller.select_channel(text)
        self.txt = ''
        self.parent.query(text=None)


    def select_toolchain(self, text: str):
        self.controller.select_platform_toolchain(text)


    def update_history(self):
        self.ent_query.clear()
        self.ent_query.addItems(self.controller.history.entries)


    def select_history(self, text: str):
        entry = self.controller.history.find(text)
        if entry:
            if entry.get('channel'):
                self.controller.select_channel(entry['channel'])
                self.update_channels()
            if entry.get('toolchain'):
                self.controller.select_platform_toolchain(entry['toolchain'])
                self.update_toolchains()
        self.parent.query()


    def show_query_context_menu(self, pos):
        self._query_menu.exec(self.ent_query.lineEdit().mapToGlobal(pos))


    def query_copy_selected_text(self):
        self.ent_query.lineEdit().copy()


    def query_copy_all_text(self):
        QApplication.clipboard().setText(self.txt)


    def query_paste_text(self):
        self.ent_query.lineEdit().paste()
