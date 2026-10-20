# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import Callable, Optional

from pygments.lexers import get_lexer_by_name
from pygments.styles import get_style_by_name

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget)

from rbbuild import data_path
from rbbuild.deps.parser import DepsParser
from rbbuild.librbb.term import term
from rbbuild.ui.config.project_control import ProjectController
from rbbuild.ui.config.project_view import ProjectView
from rbbuild.ui.config.rbbuild_control import RbbuildSettingsController
from rbbuild.ui.config.rbbuild_view import RbbuildSettingsView
from rbbuild.ui.deps.control import DepsEditorController
from rbbuild.ui.deps.view import DepsEditorView

_TOML_LEXER = get_lexer_by_name('toml')
_TOML_STYLE = get_style_by_name('default')


# Container for the whole rbbuild.toml/pyproject.toml editor: New/Open/Save
# live in RBBuildGuiApp's File menu (see rbbuild.ui.app), above an inner
# notebook of per-section sub-tabs ("project", "dependencies", "rbbuild",
# ...) and a shared whole-document Preview/Edit pane below it, built by
# threading a merged text through each section controller's
# patch_into_text() in turn. Every sub-tab's widgets and the preview are
# editable immediately; "Save" just writes the file - see
# documentation/developer-manual/gui_architecture.md.
class ConfigEditorView(QWidget):

    _MAXIMIZE_SYMBOL = '🗖'
    _RESTORE_SYMBOL = '🗗'

    def __init__(self, master: Optional[QWidget], active_deps: list, on_active_deps_change: Optional[Callable[[], None]] = None, on_loaded_path_change: Optional[Callable[[Optional[Path]], None]] = None, deps_parser: Optional[DepsParser] = None, on_jump_to_pkq: Optional[Callable[[], None]] = None):
        super().__init__(master)
        self.on_active_deps_change = on_active_deps_change
        self.on_loaded_path_change = on_loaded_path_change
        self.on_jump_to_pkq = on_jump_to_pkq
        self._preview_dirty = False
        self._document_dirty = False
        self._preview_formats = {}
        self._preview_maximized = False

        self.deps_controller = DepsEditorController(active_deps, deps_parser)
        self.project_controller = ProjectController()
        self.rbbuild_controller = RbbuildSettingsController()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self._create_info_bar(outer_layout)

        splitter = QSplitter(Qt.Vertical)
        outer_layout.addWidget(splitter, 1)
        self.splitter = splitter

        self._create_sub_notebook()
        self._create_preview()

        self._update_preview()


    def _create_info_bar(self, outer_layout: QVBoxLayout):
        info_layout = QHBoxLayout()
        outer_layout.addLayout(info_layout)

        self.lbl_dirty = QLabel('')
        self.lbl_dirty.setStyleSheet('color: #a30000; font-weight: bold;')
        info_layout.addWidget(self.lbl_dirty)
        info_layout.addStretch(1)


    def _create_sub_notebook(self):
        self.sub_notebook = QTabWidget()
        self.splitter.addWidget(self.sub_notebook)

        self.project_view = ProjectView(self.sub_notebook, self.project_controller, on_change=self._on_section_change)
        self.sub_notebook.addTab(self.project_view, 'project')

        self.deps_view = DepsEditorView(self.sub_notebook, self.deps_controller, on_change=self._on_section_change, on_jump_to_pkq=self.on_jump_to_pkq)
        self.sub_notebook.addTab(self.deps_view, 'dependencies')

        self.rbbuild_view = RbbuildSettingsView(self.sub_notebook, self.rbbuild_controller, on_change=self._on_section_change)
        self.sub_notebook.addTab(self.rbbuild_view, 'rbbuild')


    # Whole-document preview: edits only take effect once "Apply" (or
    # Save, which applies first) re-parses them back into each section's
    # model, same as opening a file. The Format combo replaces a
    # "Preview" label here - it only matters before the document is first
    # saved (see trigger_save()).
    def _create_preview(self):
        frame_preview = QWidget()
        self.splitter.addWidget(frame_preview)
        preview_layout = QVBoxLayout(frame_preview)
        preview_layout.setContentsMargins(6, 6, 6, 6)

        header_layout = QHBoxLayout()
        preview_layout.addLayout(header_layout)
        self.cmb_target_format = QComboBox()
        self.cmb_target_format.addItems(('rbbuild.toml', 'pyproject.toml'))
        self.cmb_target_format.textActivated.connect(lambda _t: self._update_preview())
        header_layout.addWidget(self.cmb_target_format)
        header_layout.addStretch(1)
        self.btn_apply_preview = QPushButton('Apply')
        self.btn_apply_preview.setEnabled(False)
        self.btn_apply_preview.clicked.connect(self._on_apply_preview)
        header_layout.addWidget(self.btn_apply_preview)
        self.btn_maximize_preview = QPushButton(self._MAXIMIZE_SYMBOL)
        self.btn_maximize_preview.setToolTip('Maximize preview')
        self.btn_maximize_preview.setFixedWidth(28)
        self.btn_maximize_preview.clicked.connect(self._on_toggle_maximize_preview)
        header_layout.addWidget(self.btn_maximize_preview)

        self.text_preview = QPlainTextEdit()
        self.text_preview.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text_preview.textChanged.connect(self._on_preview_modified)
        preview_layout.addWidget(self.text_preview, 1)

        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 2)


    # Toggles the sub-tab notebook's visibility within the splitter so the
    # preview pane can take up the whole editor; sizes are restored from
    # the splitter itself (Qt keeps them even while a widget is hidden).
    def _on_toggle_maximize_preview(self):
        self._preview_maximized = not self._preview_maximized
        self.sub_notebook.setVisible(not self._preview_maximized)
        if self._preview_maximized:
            self.btn_maximize_preview.setText(self._RESTORE_SYMBOL)
            self.btn_maximize_preview.setToolTip('Restore layout')
        else:
            self.btn_maximize_preview.setText(self._MAXIMIZE_SYMBOL)
            self.btn_maximize_preview.setToolTip('Maximize preview')


    # Threads a base text through each section controller's
    # patch_into_text() in turn. While nothing is loaded/entered yet, the
    # base text is rbbuild.toml.in (the same template `rbbuild -g` uses)
    # so a fresh editor shows a helpful example instead of a blank file.
    def _render_whole_document(self) -> str:
        text = self._blank_template_text() if self._nothing_loaded() else ''
        text = self.deps_controller.patch_into_text(text, self.cmb_target_format.currentText())
        text = self.project_controller.patch_into_text(text)
        text = self.rbbuild_controller.patch_into_text(text, self.cmb_target_format.currentText())
        return text


    def _nothing_loaded(self) -> bool:
        return (
            self.deps_controller.loaded_path is None
            and self.project_controller.loaded_path is None
            and self.rbbuild_controller.loaded_path is None)


    @staticmethod
    def _blank_template_text() -> str:
        template_path = data_path() / 'templates' / 'rbbuild.toml.in'
        try:
            return template_path.read_text(encoding='utf-8')
        except OSError:
            return ''


    # Called by every sub-tab's on_change - keeps the shared preview (and,
    # for the dependencies sub-tab, the Active Deps sidebar) in sync with
    # whatever was just edited.
    def _on_section_change(self):
        self._set_dirty(True)
        self._update_preview()
        if self.on_active_deps_change:
            self.on_active_deps_change()


    # Only re-renders from the model while there are no unapplied manual
    # edits - otherwise this would silently overwrite what the user just
    # typed (e.g. because an edit elsewhere triggered a refresh).
    def _update_preview(self):
        if self._preview_dirty:
            return
        text = self._render_whole_document()

        self.text_preview.blockSignals(True)
        self.text_preview.clear()
        cursor = self.text_preview.textCursor()
        for token_type, value in _TOML_LEXER.get_tokens(text):
            cursor.insertText(value, self._preview_format(token_type))
        self.text_preview.blockSignals(False)
        self._reset_preview_dirty()


    def _preview_format(self, token_type) -> QTextCharFormat:
        fmt = self._preview_formats.get(token_type)
        if fmt is None:
            fmt = QTextCharFormat()
            color = _TOML_STYLE.style_for_token(token_type)['color']
            if color:
                fmt.setForeground(QColor(f'#{color}'))
            self._preview_formats[token_type] = fmt
        return fmt


    # textChanged also fires for our own programmatic rewrites in
    # _update_preview()/_on_apply_preview() - those are wrapped in
    # blockSignals(), so only genuine user edits reach this handler.
    def _on_preview_modified(self):
        self._preview_dirty = True
        self._set_dirty(True)
        self.btn_apply_preview.setEnabled(True)


    # Re-parses the (possibly hand-edited) preview text back into every
    # section's model, same as opening a file - refreshes every sub-tab to
    # match. Returns True on success, False if the text didn't parse (the
    # dirty edits are left in place either way, so nothing is lost).
    def _on_apply_preview(self) -> bool:
        text = self.text_preview.toPlainText()
        target_filename = self.cmb_target_format.currentText()
        try:
            self.deps_controller.load_from_text(text, target_filename)
            self.project_controller.load_from_text(text)
            self.rbbuild_controller.load_from_text(text, target_filename)
        except Exception as exc:
            term.error('failed to parse preview', exc)
            return False

        self._reset_preview_dirty()
        self._reload_sub_tabs()
        if self.on_active_deps_change:
            self.on_active_deps_change()
        return True


    # Save (and any programmatic model change that's about to re-render
    # the preview) must not silently discard unapplied manual edits -
    # apply them first, aborting the caller's action if they don't parse.
    def _ensure_preview_applied(self) -> bool:
        if not self._preview_dirty:
            return True
        return self._on_apply_preview()


    def _reset_preview_dirty(self):
        self._preview_dirty = False
        self.btn_apply_preview.setEnabled(False)


    def _set_dirty(self, dirty: bool):
        self._document_dirty = dirty
        self.lbl_dirty.setText('Unsaved changes' if dirty else '')


    def _reload_sub_tabs(self):
        self.deps_view.reload()
        self.project_view.reload()
        self.rbbuild_view.reload()


    def trigger_open(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, 'Open rbbuild.toml/pyproject.toml', '',
            'TOML files (*.toml);;All files (*.*)')
        if not path:
            return

        try:
            self.deps_controller.open_file(path)
            self.project_controller.open_file(path)
            self.rbbuild_controller.open_file(path)
        except Exception as exc:
            term.error('failed to open', exc)
            return

        if Path(path).name in ('rbbuild.toml', 'pyproject.toml'):
            self.cmb_target_format.setCurrentText(Path(path).name)
        self._reset_preview_dirty()
        self._set_dirty(False)
        self._notify_loaded_path()
        self._reload_sub_tabs()
        self._update_preview()
        if self.on_active_deps_change:
            self.on_active_deps_change()
        term.info(f'Loaded {path}')


    # Starts a fresh document for target_filename ('rbbuild.toml' or
    # 'pyproject.toml', chosen via RBBuildGuiApp's File > New Workspace
    # submenu) - confirms first if there's anything to lose, then asks for
    # a destination folder and writes the file there immediately.
    def trigger_new(self, target_filename: str):
        has_content = (
            self.deps_controller.active_deps
            or self.deps_controller.loaded_path is not None
            or self.project_controller.loaded_path is not None
            or self.rbbuild_controller.loaded_path is not None)
        if has_content:
            if QMessageBox.question(
                    self, 'Discard current document?',
                    'Starting a new file will discard everything '
                    'currently loaded/entered. Continue?') != QMessageBox.Yes:
                return

        directory = self._choose_target_folder(
            'Choose folder for the new workspace')
        if directory is None:
            return

        self.cmb_target_format.setCurrentText(target_filename)
        self.deps_controller.new_document(target_filename)
        self.project_controller.new_document()
        self.rbbuild_controller.new_document()
        self._reset_preview_dirty()
        self._reload_sub_tabs()
        self._update_preview()
        if self.on_active_deps_change:
            self.on_active_deps_change()

        self._save_to(str(directory / target_filename))


    def _choose_target_folder(self, title: str) -> Optional[Path]:
        directory = QFileDialog.getExistingDirectory(self, title, str(Path.home()))
        return Path(directory) if directory else None


    # Saves the current document, applying any unapplied manual preview
    # edits first. Prompts for a destination folder the first time
    # (nothing loaded/saved yet), using the Format selection; subsequent
    # saves reuse that same path. Save never renames an already-loaded
    # file - if the Format selection no longer matches it, the previous
    # format wins and a warning is issued; use "Save As" to actually
    # switch format.
    def trigger_save(self):
        if not self._ensure_preview_applied():
            return

        target_filename = self.cmb_target_format.currentText()
        loaded_path = self.deps_controller.loaded_path
        if loaded_path is None:
            directory = self._choose_target_folder('Choose folder to save into')
            if directory is None:
                return
            path = str(directory / target_filename)
        else:
            path = str(loaded_path)
            loaded_filename = Path(loaded_path).name
            if (loaded_filename in ('rbbuild.toml', 'pyproject.toml')
                    and target_filename != loaded_filename):
                term.warning(
                    f'Save cannot switch format from {loaded_filename} to '
                    f'{target_filename}; saving as {loaded_filename} '
                    'instead. Use File > Save As to change format.')
                self.cmb_target_format.setCurrentText(loaded_filename)

        self._save_to(path)


    # Lets the user explicitly switch an existing document's on-disk
    # format (Save refuses to - see trigger_save()) by writing it out
    # under a new filename in a chosen folder; each controller re-derives
    # its own table from that filename, same as opening a file fresh.
    def trigger_save_as(self, target_filename: str):
        if not self._ensure_preview_applied():
            return

        directory = self._choose_target_folder(
            f'Save As {target_filename} - choose folder')
        if directory is None:
            return

        self.cmb_target_format.setCurrentText(target_filename)
        self._save_to(str(directory / target_filename))


    # Each controller independently reads-modifies-writes the same file in
    # turn, so their tables are folded into one another exactly like
    # patch_into_text() does for the in-memory preview.
    def _save_to(self, path):
        try:
            self.deps_controller.save_file(path)
            self.project_controller.save_file(path)
            self.rbbuild_controller.save_file(path)
        except Exception as exc:
            term.error('failed to save', exc)
            return

        self._set_dirty(False)
        self._notify_loaded_path()
        self._update_preview()
        term.info(f'Saved to {path}')


    def _notify_loaded_path(self):
        if self.on_loaded_path_change:
            self.on_loaded_path_change(self.deps_controller.loaded_path)


    # Repopulates the dependencies sub-tab's own list - called by
    # RBBuildGuiApp.refresh_active_deps() whenever active_deps changes from
    # outside this view (e.g. drag-and-drop from the Package Query tab).
    def refresh_active_deps(self):
        self.deps_view.refresh_list()
        self._update_preview()
