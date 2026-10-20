# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Callable, Optional

from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QLineEdit, QVBoxLayout, QWidget)

from rbbuild.ui.config.project_control import ProjectController


# "project" sub-tab of the rbbuild.toml editor (see
# rbbuild.ui.config.view.ConfigEditorView): the [project] table's simple
# fields. License, authors/maintainers and scripts/gui-scripts aren't
# shown here (edit those directly in the preview) - the controller still
# models them so an opened file's values round-trip on save. on_change is
# called after every edit, so the container can refresh the shared
# whole-document preview.
class ProjectView(QWidget):

    _SIMPLE_FIELDS = (
        ('name', 'name'), ('version', 'version'), ('branch', 'branch'))

    def __init__(self, master: Optional[QWidget], controller: ProjectController, on_change: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.controller = controller
        self.on_change = on_change
        self._simple_edits = {}

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        self._create_general(outer_layout)
        outer_layout.addStretch(1)

        self.reload()


    def _create_general(self, outer_layout: QVBoxLayout):
        group = QGroupBox('General')
        outer_layout.addWidget(group)
        form = QFormLayout(group)

        for key, label in self._SIMPLE_FIELDS:
            edit = QLineEdit()
            edit.editingFinished.connect(self._apply)
            form.addRow(label, edit)
            self._simple_edits[key] = edit


    # Refreshes every field from the controller's current state - used by
    # ConfigEditorView after loading a new document (Open/New/Apply
    # preview edits).
    def reload(self):
        for key, _ in self._SIMPLE_FIELDS:
            self._simple_edits[key].setText(getattr(self.controller, key) or '')


    def _apply(self):
        for key, _ in self._SIMPLE_FIELDS:
            setattr(self.controller, key, self._simple_edits[key].text() or None)

        if self.on_change:
            self.on_change()
