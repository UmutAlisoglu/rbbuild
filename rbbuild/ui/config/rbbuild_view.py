# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Callable, List, Optional

from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QVBoxLayout, QWidget)

from rbbuild.ui.config.rbbuild_control import RbbuildSettingsController


# "rbbuild" sub-tab of the rbbuild.toml editor (see
# rbbuild.ui.config.view.ConfigEditorView): the [rbbuild] table's actions/
# build-tools/documentation-tools/test-tools/sca-tools. All but build-tools
# are shown as plain checkbox sets - small fixed enumerations whose list
# order has no effect at runtime (see documentation/user-manual/rbbuild.toml.md).
# build_tools also gets an ordered list + Up/Down buttons, since
# build_tools() (__main__.py) invokes each tool in list order for
# build/install/clean/package. on_change is called after every edit, so
# the container can refresh the shared whole-document preview.
class RbbuildSettingsView(QWidget):

    # Excludes 'execute', which takes an argument rather than being a
    # simple on/off toggle (see parse_command_line() in __main__.py).
    _ACTIONS = (
        'setup', 'build', 'install', 'package', 'clean', 'fetch',
        'install_deps', 'run_tests', 'static_code_analysis',
        'documentation', 'publish')
    _BUILD_TOOLS = ('rbbuild', 'cmake', 'pypa', 'npm')
    _DOCUMENTATION_TOOLS = ('pandoc', 'sphinx')
    _TEST_TOOLS = ('ctest', 'pytest')
    _SCA_TOOLS = ('ruff',)

    # rbbuild falls back to these when a project's own config doesn't set
    # actions/build_tools at all - see share/rbbuild/config/rbbuild.toml.
    # Shown pre-checked so the tab reflects what actually runs by default.
    _DEFAULT_ACTIONS = ('setup', 'build')
    _DEFAULT_BUILD_TOOLS = ('rbbuild', 'cmake', 'pypa', 'npm')
    _DEFAULT_SCA_TOOLS = ('ruff',)

    def __init__(self, master: Optional[QWidget], controller: RbbuildSettingsController, on_change: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.controller = controller
        self.on_change = on_change

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)

        self._create_checkbox_set(outer_layout, 'actions', 'Actions', self._ACTIONS)
        self._create_build_tools_section(outer_layout)
        self._create_checkbox_set(outer_layout, 'documentation_tools', 'Documentation tools', self._DOCUMENTATION_TOOLS)
        self._create_checkbox_set(outer_layout, 'test_tools', 'Test tools', self._TEST_TOOLS)
        self._create_checkbox_set(outer_layout, 'sca_tools', 'SCA tools', self._SCA_TOOLS)
        outer_layout.addStretch(1)

        self.reload()


    # Shared by actions/documentation_tools - both are small fixed
    # enumerations whose order doesn't matter, so a checkbox each is
    # simpler than a free-text list. Wraps to a new row every 4 checkboxes.
    def _create_checkbox_set(self, outer_layout: QVBoxLayout, field: str, title: str, values):
        group = QGroupBox(title)
        outer_layout.addWidget(group)
        grid = QGridLayout(group)

        columns = 4
        checkboxes = {}
        for index, value in enumerate(values):
            chk = QCheckBox(value)
            chk.stateChanged.connect(self._apply)
            grid.addWidget(chk, index // columns, index % columns)
            checkboxes[value] = chk

        setattr(self, f'_{field}_checkboxes', checkboxes)


    # build_tools needs an explicit order (unlike the plain checkbox
    # sets), since it controls which package manager runs first for
    # build/install/clean/package - a checkbox alone can't express that.
    # self._build_tools_order holds the currently-checked tools in the
    # order they'll be written; the list widget mirrors it read-only, and
    # Up/Down swap the selected entry with its neighbour.
    def _create_build_tools_section(self, outer_layout: QVBoxLayout):
        group = QGroupBox('Build tools')
        outer_layout.addWidget(group)
        row_layout = QHBoxLayout(group)

        checks_layout = QVBoxLayout()
        row_layout.addLayout(checks_layout)

        self._build_tools_checkboxes = {}
        for value in self._BUILD_TOOLS:
            chk = QCheckBox(value)
            chk.stateChanged.connect(lambda _state, v=value: self._on_toggle_build_tool(v))
            checks_layout.addWidget(chk)
            self._build_tools_checkboxes[value] = chk
        checks_layout.addStretch(1)

        order_layout = QVBoxLayout()
        row_layout.addLayout(order_layout, 1)
        order_layout.addWidget(QLabel('Order (top runs first)'))

        order_row_layout = QHBoxLayout()
        order_layout.addLayout(order_row_layout)
        self.list_build_tools_order = QListWidget()
        self.list_build_tools_order.setFixedHeight(90)
        order_row_layout.addWidget(self.list_build_tools_order, 1)

        order_buttons_layout = QVBoxLayout()
        order_row_layout.addLayout(order_buttons_layout)
        btn_up = QPushButton('Up')
        btn_up.clicked.connect(self._on_move_build_tool_up)
        order_buttons_layout.addWidget(btn_up)
        btn_down = QPushButton('Down')
        btn_down.clicked.connect(self._on_move_build_tool_down)
        order_buttons_layout.addWidget(btn_down)
        order_buttons_layout.addStretch(1)

        self._build_tools_order: List[str] = []


    def _on_toggle_build_tool(self, value: str):
        if self._build_tools_checkboxes[value].isChecked():
            if value not in self._build_tools_order:
                self._build_tools_order.append(value)
        elif value in self._build_tools_order:
            self._build_tools_order.remove(value)

        self._refresh_build_tools_order_list()
        self._apply()


    def _on_move_build_tool_up(self):
        self._move_build_tool(-1)


    def _on_move_build_tool_down(self):
        self._move_build_tool(1)


    def _move_build_tool(self, offset: int):
        index = self.list_build_tools_order.currentRow()
        if index < 0:
            return

        new_index = index + offset
        if not (0 <= new_index < len(self._build_tools_order)):
            return

        order = self._build_tools_order
        order[index], order[new_index] = order[new_index], order[index]
        self._refresh_build_tools_order_list()
        self.list_build_tools_order.setCurrentRow(new_index)
        self._apply()


    def _refresh_build_tools_order_list(self):
        self.list_build_tools_order.clear()
        self.list_build_tools_order.addItems(self._build_tools_order)


    # Refreshes every field from the controller's current state - used by
    # ConfigEditorView after loading a new document (Open/New/Apply
    # preview edits). If actions/build_tools come back empty (key absent
    # from the file, or a brand new document), materialize rbbuild's own
    # fallback defaults into the controller so the checkboxes shown here
    # match what would actually run, and Save persists them explicitly.
    #
    # Checkboxes are updated with signals blocked.
    def reload(self):
        if not self.controller.actions:
            self.controller.actions = list(self._DEFAULT_ACTIONS)
        if not self.controller.build_tools:
            self.controller.build_tools = list(self._DEFAULT_BUILD_TOOLS)
        if not self.controller.sca_tools:
            self.controller.sca_tools = list(self._DEFAULT_SCA_TOOLS)

        for value, chk in self._actions_checkboxes.items():
            chk.blockSignals(True)
            chk.setChecked(value in self.controller.actions)
            chk.blockSignals(False)

        for value, chk in self._build_tools_checkboxes.items():
            chk.blockSignals(True)
            chk.setChecked(value in self.controller.build_tools)
            chk.blockSignals(False)
        self._build_tools_order = [
            value for value in self.controller.build_tools
            if value in self._build_tools_checkboxes]
        self._refresh_build_tools_order_list()

        for value, chk in self._documentation_tools_checkboxes.items():
            chk.blockSignals(True)
            chk.setChecked(value in self.controller.documentation_tools)
            chk.blockSignals(False)

        for value, chk in self._test_tools_checkboxes.items():
            chk.blockSignals(True)
            chk.setChecked(value in self.controller.test_tools)
            chk.blockSignals(False)

        for value, chk in self._sca_tools_checkboxes.items():
            chk.blockSignals(True)
            chk.setChecked(value in self.controller.sca_tools)
            chk.blockSignals(False)


    def _apply(self):
        self.controller.actions = [value for value, chk in self._actions_checkboxes.items() if chk.isChecked()]
        self.controller.build_tools = list(self._build_tools_order)
        self.controller.documentation_tools = [
            value for value, chk in self._documentation_tools_checkboxes.items() if chk.isChecked()]
        self.controller.test_tools = [value for value, chk in self._test_tools_checkboxes.items() if chk.isChecked()]
        self.controller.sca_tools = [value for value, chk in self._sca_tools_checkboxes.items() if chk.isChecked()]

        if self.on_change:
            self.on_change()
