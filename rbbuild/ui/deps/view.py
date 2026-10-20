# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QPushButton, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)

from rbbuild.package.package import IntegrationType, Package
from rbbuild.package.type import PackageType
from rbbuild.ui.deps.control import DepsEditorController


# QPlainTextEdit has no editingFinished signal - needed for the Comment
# field, which (like the other detail-form fields) applies on focus-out
# rather than on every keystroke.
class _CommentEdit(QPlainTextEdit):

    def __init__(self, on_focus_out: Callable[[], None]):
        super().__init__()
        self._on_focus_out = on_focus_out


    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._on_focus_out()


# Dependencies sub-tab of the rbbuild.toml editor (see
# rbbuild.ui.config.view.ConfigEditorView): a "Section settings" panel for
# section-wide attributes (top), a list of the shared active_deps Package
# objects (bottom left) and a detail form for the selected entry's flags/
# SBOM metadata (bottom right). Removing an entry is done via the Remove
# button below the list (see remove_selected()/has_selection below);
# double-clicking an entry jumps to the pkq dependency picker, same as Add.
# The whole-document Preview/Edit pane is owned by the container, not here.
# on_change, if given, is called after every list-membership change (e.g.
# remove) so the caller can refresh other views of the same document (see
# RBBuildGuiApp.refresh_active_deps()) and the shared preview.
class DepsEditorView(QWidget):

    _INTEGRATION_TYPES = [''] + [str(t) for t in IntegrationType]
    _COMPONENT_TYPES = [str(t) for t in PackageType]
    _PACKAGE_INSTALL_ACTIONS = ['', 'copy']

    def __init__(self, master: Optional[QWidget], controller: DepsEditorController, on_change: Optional[Callable[[], None]] = None, on_jump_to_pkq: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.controller = controller
        self.on_change = on_change
        self.on_jump_to_pkq = on_jump_to_pkq

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._create_section_settings(outer_layout)

        splitter_lists = QSplitter(Qt.Horizontal)
        outer_layout.addWidget(splitter_lists, 1)

        self._create_list(splitter_lists)
        self._create_detail_form(splitter_lists)

        self.reload()


    # Section-wide attributes (as opposed to a single entry's) - namespace/
    # installdir and the flags documented for [[dependencies]] sections.
    def _create_section_settings(self, outer_layout: QVBoxLayout):
        group = QGroupBox('Section settings')
        outer_layout.addWidget(group)
        form = QFormLayout(group)

        self.entry_namespace = QLineEdit()
        self.entry_namespace.editingFinished.connect(self._apply_section_attrs)
        form.addRow('namespace', self.entry_namespace)

        self.entry_installdir = QLineEdit()
        self.entry_installdir.editingFinished.connect(self._apply_section_attrs)
        form.addRow('installdir', self.entry_installdir)

        self.entry_restrict_platform = QLineEdit()
        self.entry_restrict_platform.editingFinished.connect(self._apply_section_attrs)
        form.addRow('restrict_platform', self.entry_restrict_platform)

        self.entry_restrict_toolchain = QLineEdit()
        self.entry_restrict_toolchain.editingFinished.connect(self._apply_section_attrs)
        form.addRow('restrict_toolchain', self.entry_restrict_toolchain)

        self.entry_section_components = QLineEdit()
        self.entry_section_components.editingFinished.connect(self._apply_section_attrs)
        form.addRow('components', self.entry_section_components)

        self.cmb_package_install_action = self._readonly_combo(self._PACKAGE_INSTALL_ACTIONS)
        self.cmb_package_install_action.textActivated.connect(lambda _t: self._apply_section_attrs())
        form.addRow('package_install_action', self.cmb_package_install_action)

        checks_layout = QHBoxLayout()
        self.chk_section_build_only = QCheckBox('build_only')
        self.chk_section_build_only.stateChanged.connect(self._apply_section_attrs)
        checks_layout.addWidget(self.chk_section_build_only)
        self.chk_section_traverse = QCheckBox('traverse')
        self.chk_section_traverse.stateChanged.connect(self._apply_section_attrs)
        checks_layout.addWidget(self.chk_section_traverse)
        checks_layout.addStretch(1)
        form.addRow(checks_layout)


    @staticmethod
    def _readonly_combo(values):
        combo = QComboBox()
        combo.addItems(values)
        return combo


    def _load_section_settings(self):
        attrs = self.controller.get_section_attrs()
        self.entry_namespace.setText(attrs.get('namespace', ''))
        self.entry_installdir.setText(attrs.get('installdir', ''))
        self.entry_restrict_platform.setText(attrs.get('restrict_platform', ''))
        self.entry_restrict_toolchain.setText(attrs.get('restrict_toolchain', ''))
        components = attrs.get('components', [])
        self.entry_section_components.setText(','.join(components) if isinstance(components, list) else str(components))
        self.chk_section_build_only.blockSignals(True)
        self.chk_section_build_only.setChecked(bool(attrs.get('build_only')))
        self.chk_section_build_only.blockSignals(False)
        self.chk_section_traverse.blockSignals(True)
        self.chk_section_traverse.setChecked(
            attrs.get('traverse', True) is not False
            and not attrs.get('no_traverse'))
        self.chk_section_traverse.blockSignals(False)
        self.cmb_package_install_action.setCurrentText(attrs.get('package_install_action', ''))


    def _apply_section_attrs(self):
        components = [c.strip() for c in self.entry_section_components.text().split(',') if c.strip()]
        self.controller.apply_section_attrs(
            namespace=self.entry_namespace.text(),
            installdir=self.entry_installdir.text(),
            restrict_platform=self.entry_restrict_platform.text(),
            restrict_toolchain=self.entry_restrict_toolchain.text(),
            components=components,
            build_only=self.chk_section_build_only.isChecked(),
            traverse=self.chk_section_traverse.isChecked(),
            package_install_action=self.cmb_package_install_action.currentText())
        if self.on_change:
            self.on_change()


    def _create_list(self, splitter_lists: QSplitter):
        frame_list = QWidget()
        splitter_lists.addWidget(frame_list)
        list_layout = QVBoxLayout(frame_list)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.tree_list = QTreeWidget()
        self.tree_list.setHeaderLabels(['Dependencies'])
        self.tree_list.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree_list.setRootIsDecorated(False)
        self.tree_list.itemSelectionChanged.connect(self._on_select)
        self.tree_list.itemDoubleClicked.connect(lambda _item, _col: self._on_add_dependency())
        list_layout.addWidget(self.tree_list, 1)

        buttons_row = QHBoxLayout()
        btn_add = QPushButton('Add')
        btn_add.clicked.connect(self._on_add_dependency)
        buttons_row.addWidget(btn_add)
        btn_remove = QPushButton('Remove')
        btn_remove.clicked.connect(self.remove_selected)
        buttons_row.addWidget(btn_remove)
        list_layout.addLayout(buttons_row)


    def _on_add_dependency(self):
        if self.on_jump_to_pkq:
            self.on_jump_to_pkq()


    def _create_detail_form(self, splitter_lists: QSplitter):
        frame_detail = QWidget()
        splitter_lists.addWidget(frame_detail)
        detail_layout = QVBoxLayout(frame_detail)
        detail_layout.setContentsMargins(6, 6, 6, 6)

        group_flags = QGroupBox('Flags')
        detail_layout.addWidget(group_flags)
        flags_layout = QVBoxLayout(group_flags)

        checks_row = QHBoxLayout()
        self.chk_build_only = QCheckBox('build_only')
        self.chk_build_only.stateChanged.connect(self._apply_flags)
        checks_row.addWidget(self.chk_build_only)
        self.chk_traverse = QCheckBox('traverse')
        self.chk_traverse.setChecked(True)
        self.chk_traverse.stateChanged.connect(self._apply_flags)
        checks_row.addWidget(self.chk_traverse)
        checks_row.addStretch(1)
        flags_layout.addLayout(checks_row)

        flags_form = QFormLayout()
        flags_layout.addLayout(flags_form)
        self.entry_components = QLineEdit()
        self.entry_components.editingFinished.connect(self._apply_flags)
        flags_form.addRow('components', self.entry_components)
        self.entry_suffixes = QLineEdit()
        self.entry_suffixes.editingFinished.connect(self._apply_flags)
        flags_form.addRow('suffixes', self.entry_suffixes)

        group_sbom = QGroupBox('SBOM')
        detail_layout.addWidget(group_sbom)
        sbom_form = QFormLayout(group_sbom)

        self.entry_cpe = QLineEdit()
        self.entry_cpe.editingFinished.connect(self._apply_sbom)
        sbom_form.addRow('cpe', self.entry_cpe)

        self.entry_copyright = QLineEdit()
        self.entry_copyright.editingFinished.connect(self._apply_sbom)
        sbom_form.addRow('copyright', self.entry_copyright)

        self.entry_licenses = QLineEdit()
        self.entry_licenses.editingFinished.connect(self._apply_sbom)
        sbom_form.addRow('licenses (SPDX expression)', self.entry_licenses)

        self.cmb_integration_type = self._readonly_combo(self._INTEGRATION_TYPES)
        self.cmb_integration_type.textActivated.connect(lambda _t: self._apply_sbom())
        sbom_form.addRow('integration_type', self.cmb_integration_type)

        self.cmb_component_type = self._readonly_combo(self._COMPONENT_TYPES)
        self.cmb_component_type.textActivated.connect(lambda _t: self._apply_sbom())
        sbom_form.addRow('component_type', self.cmb_component_type)

        self.entry_supplier_name = QLineEdit()
        self.entry_supplier_name.editingFinished.connect(self._apply_sbom)
        sbom_form.addRow('supplier.name', self.entry_supplier_name)

        self.entry_supplier_email = QLineEdit()
        self.entry_supplier_email.editingFinished.connect(self._apply_sbom)
        sbom_form.addRow('supplier.email', self.entry_supplier_email)

        self.entry_supplier_url = QLineEdit()
        self.entry_supplier_url.editingFinished.connect(self._apply_sbom)
        sbom_form.addRow('supplier.url', self.entry_supplier_url)

        group_comment = QGroupBox('Comment')
        detail_layout.addWidget(group_comment)
        comment_layout = QVBoxLayout(group_comment)
        self.text_comment = _CommentEdit(self._apply_comment)
        self.text_comment.setFixedHeight(60)
        comment_layout.addWidget(self.text_comment)

        detail_layout.addStretch(1)
        self.frame_detail = frame_detail
        self._detail_widgets = [
            self.chk_build_only, self.chk_traverse,
            self.entry_components, self.entry_suffixes,
            self.entry_cpe, self.entry_copyright, self.entry_licenses,
            self.cmb_integration_type, self.cmb_component_type,
            self.entry_supplier_name, self.entry_supplier_email,
            self.entry_supplier_url, self.text_comment,
        ]


    def refresh_list(self):
        selected = self.controller.selected
        self.tree_list.clear()
        for item in self.controller.active_deps:
            self.tree_list.addTopLevelItem(QTreeWidgetItem([str(item)]))
        if selected in self.controller.active_deps:
            index = self.controller.active_deps.index(selected)
            top_item = self.tree_list.topLevelItem(index)
            self.tree_list.setCurrentItem(top_item)


    # Refreshes list/detail-form/section-settings from the controller's
    # current state in one go - used by ConfigEditorView after loading a
    # new document (Open/New/Apply preview edits).
    def reload(self):
        self.refresh_list()
        self._load_into_form(None)
        self._load_section_settings()


    def _on_select(self):
        index = self.tree_list.indexOfTopLevelItem(self.tree_list.currentItem())
        if index < 0:
            self._load_into_form(None)
            self._load_section_settings()
            return

        self.controller.select(index)
        self._load_into_form(self.controller.selected)
        self._load_section_settings()


    @property
    def has_selection(self) -> bool:
        return self.controller.selected is not None


    # Called from RBBuildGuiApp's Edit > Remove Dependency menu command.
    def remove_selected(self):
        if self.controller.selected is None:
            return
        self.controller.remove_selected()
        self.reload()
        if self.on_change:
            self.on_change()


    def _load_into_form(self, pkg: Optional[Package]):
        for widget in self._detail_widgets:
            widget.setEnabled(pkg is not None)

        self.text_comment.setPlainText(self.controller.get_comment(pkg) if pkg is not None else '')

        if pkg is None:
            return

        spec_values = {}
        if pkg.component_specifier is not None and pkg.component_specifier.items:
            spec_values = next(iter(pkg.component_specifier.items.values()))
        self.chk_build_only.blockSignals(True)
        self.chk_build_only.setChecked(bool(spec_values.get('build_only')))
        self.chk_build_only.blockSignals(False)
        self.chk_traverse.blockSignals(True)
        self.chk_traverse.setChecked(spec_values.get('traverse', True))
        self.chk_traverse.blockSignals(False)

        components = set()
        suffixes = set()
        if pkg.component_specifier is not None:
            for component, suffix in pkg.component_specifier.items:
                if component:
                    components.add(component)
                if suffix:
                    suffixes.add(suffix)
        self.entry_components.setText(','.join(sorted(components)))
        self.entry_suffixes.setText(','.join(sorted(suffixes)))

        self.entry_cpe.setText(pkg.cpe or '')
        self.entry_copyright.setText(pkg.copyright or '')
        self.entry_licenses.setText(','.join(str(lic) for lic in pkg.licenses) if pkg.licenses else '')
        self.cmb_integration_type.setCurrentText(str(pkg.integration_type) if pkg.integration_type is not None else '')
        self.cmb_component_type.setCurrentText(str(pkg.component_type))

        supplier = pkg.supplier
        self.entry_supplier_name.setText(supplier.name or '' if supplier else '')
        self.entry_supplier_email.setText(supplier.email or '' if supplier else '')
        self.entry_supplier_url.setText(supplier.url or '' if supplier else '')


    def _apply_flags(self):
        if self.controller.selected is None:
            return
        self.controller.apply_flags(
            self.chk_build_only.isChecked(), self.chk_traverse.isChecked(),
            self.entry_components.text(), self.entry_suffixes.text())
        self.refresh_list()
        if self.on_change:
            self.on_change()


    def _apply_sbom(self):
        if self.controller.selected is None:
            return
        self.controller.apply_sbom(
            self.entry_cpe.text(), self.entry_copyright.text(), self.entry_licenses.text(),
            self.cmb_integration_type.currentText(), self.cmb_component_type.currentText(),
            self.entry_supplier_name.text(), self.entry_supplier_email.text(), self.entry_supplier_url.text())
        if self.on_change:
            self.on_change()


    def _apply_comment(self):
        if self.controller.selected is None:
            return
        self.controller.apply_comment(self.text_comment.toPlainText())
        if self.on_change:
            self.on_change()

