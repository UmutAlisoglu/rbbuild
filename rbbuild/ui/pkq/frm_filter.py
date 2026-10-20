# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

if TYPE_CHECKING:
    from rbbuild.ui.pkq.view import PkqView


# Filter bar. Two mutually-exclusive sets of controls, toggled by
# set_diff_mode(): normal query (text filter + collapse + Problems) or
# version-range diff (Swap versions + per-state checkboxes).
class PkqFilterFrame:

    def __init__(self, parent: 'PkqView', master: QWidget):
        self.master = master
        self.parent = parent
        self._frm = self._create_frm(master)


    @property
    def frm(self) -> QWidget:
        return self._frm


    def _create_frm(self, master: QWidget) -> QWidget:
        frm_filter = QWidget(master)
        layout = QHBoxLayout(frm_filter)
        layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_filter = QLabel('Filter')
        layout.addWidget(self.lbl_filter)

        self.ent_filter = QLineEdit()
        self.ent_filter.textChanged.connect(lambda _text: self.parent.display_packages())
        layout.addWidget(self.ent_filter, 1)

        self.chk_collapse = QCheckBox('Collapse')
        self.chk_collapse.stateChanged.connect(lambda _state: self.parent.display_packages())
        layout.addWidget(self.chk_collapse)

        self.chk_problems = QCheckBox('Problems')
        self.chk_problems.stateChanged.connect(lambda _state: self.parent.display_packages())
        layout.addWidget(self.chk_problems)

        self._normal_mode_widgets = (self.lbl_filter, self.ent_filter, self.chk_collapse, self.chk_problems)

        # 'same' is off by default, the rest on.
        self.btn_swap = QPushButton('Swap versions')
        self.btn_swap.clicked.connect(self.parent.swap_compare_versions)
        layout.addWidget(self.btn_swap)

        self.chk_changed = QCheckBox('Changed')
        self.chk_changed.setChecked(True)
        self.chk_changed.stateChanged.connect(lambda _state: self.parent.display_packages())
        layout.addWidget(self.chk_changed)

        self.chk_new = QCheckBox('New')
        self.chk_new.setChecked(True)
        self.chk_new.stateChanged.connect(lambda _state: self.parent.display_packages())
        layout.addWidget(self.chk_new)

        self.chk_deleted = QCheckBox('Deleted')
        self.chk_deleted.setChecked(True)
        self.chk_deleted.stateChanged.connect(lambda _state: self.parent.display_packages())
        layout.addWidget(self.chk_deleted)

        self.chk_same = QCheckBox('Same')
        self.chk_same.setChecked(False)
        self.chk_same.stateChanged.connect(lambda _state: self.parent.display_packages())
        layout.addWidget(self.chk_same)

        self._diff_mode_widgets = (self.btn_swap, self.chk_changed, self.chk_new, self.chk_deleted, self.chk_same)

        layout.addStretch(1)

        self.set_diff_mode(False, has_tree=False)

        return frm_filter


    # Shows the controls relevant to the current display, hiding the other
    # set. has_tree is False for flat name/version listings (Mode 1/2 in
    # Query), which have nothing to filter/collapse - the whole row is
    # hidden in that case.
    def set_diff_mode(self, diff_mode: bool, has_tree: bool = True):
        if diff_mode:
            for widget in self._normal_mode_widgets:
                widget.setVisible(False)
            for widget in self._diff_mode_widgets:
                widget.setVisible(True)
        elif has_tree:
            for widget in self._diff_mode_widgets:
                widget.setVisible(False)
            for widget in self._normal_mode_widgets:
                widget.setVisible(True)
        else:
            for widget in self._normal_mode_widgets + self._diff_mode_widgets:
                widget.setVisible(False)


    @property
    def collapse(self) -> bool:
        return self.chk_collapse.isChecked()


    @property
    def problems(self) -> bool:
        return self.chk_problems.isChecked()


    @property
    def txt(self) -> str:
        return self.ent_filter.text()


    # Compare-state names enabled by the diff-mode checkboxes, used to filter the changes list.
    @property
    def enabled_states(self) -> set:
        states = set()
        if self.chk_changed.isChecked():
            states.add('changed')
        if self.chk_new.isChecked():
            states.add('new')
        if self.chk_deleted.isChecked():
            states.add('deleted')
        if self.chk_same.isChecked():
            states.add('same')
        return states
