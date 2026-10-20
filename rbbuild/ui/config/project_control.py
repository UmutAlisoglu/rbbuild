# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import tomlkit
from pathlib import Path
from typing import Dict, List, Optional, Union

from rbbuild.toml_template import strip_commented_placeholder


# Business logic for the "project" sub-tab of the rbbuild.toml editor,
# covering the [project] table - the same table name for both
# rbbuild.toml and pyproject.toml (unlike [dependencies]/
# [tool.rbbuild.dependencies], [project] isn't nested when read from
# pyproject.toml - see documentation/user-manual/rbbuild.toml.md and
# RBBuildConfiguration._load_pyproject_toml()). Kept UI-framework-free so
# it can be unit tested directly, matching DepsEditorController.
class ProjectController:

    _SIMPLE_FIELDS = (
        'name', 'branch', 'version', 'version_major', 'version_minor',
        'version_revision', 'version_build')

    _ALL_FIELDS = _SIMPLE_FIELDS + (
        'authors', 'maintainers', 'license', 'scripts', 'gui-scripts')

    def __init__(self):
        self.loaded_path: Optional[Path] = None
        self.new_document()


    def new_document(self):
        for key in self._SIMPLE_FIELDS:
            setattr(self, key, None)
        self.authors: List[dict] = []
        self.maintainers: List[dict] = []
        self.license: dict = {}
        self.scripts: Dict[str, str] = {}
        self.gui_scripts: Dict[str, str] = {}
        self.loaded_path = None


    def open_file(self, path: Union[str, Path]):
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as fd:
            text = fd.read()

        self._load_from_text(text)
        self.loaded_path = path


    # Re-parses arbitrary TOML text (e.g. a user-edited whole-document
    # preview) into the model in place - same as open_file(), but doesn't
    # touch loaded_path.
    def load_from_text(self, text: str):
        self._load_from_text(text)


    def _load_from_text(self, text: str):
        doc = tomlkit.parse(text) if text.strip() else tomlkit.document()
        project = doc.get('project', {})

        for key in self._SIMPLE_FIELDS:
            value = project.get(key)
            setattr(self, key, str(value) if value is not None else None)

        self.authors = [dict(item) for item in project.get('authors', [])]
        self.maintainers = [dict(item) for item in project.get('maintainers', [])]
        self.license = dict(project.get('license', {}))
        self.scripts = dict(project.get('scripts', {}))
        self.gui_scripts = dict(project.get('gui-scripts', {}))


    def _collect_values(self) -> dict:
        values = {}
        for key in self._SIMPLE_FIELDS:
            value = getattr(self, key)
            if value not in (None, ''):
                values[key] = value

        if self.authors:
            values['authors'] = self.authors
        if self.maintainers:
            values['maintainers'] = self.maintainers
        if self.license:
            values['license'] = self.license
        if self.scripts:
            values['scripts'] = self.scripts
        if self.gui_scripts:
            values['gui-scripts'] = self.gui_scripts

        return values


    # Folds the [project] table into base_text, preserving every other
    # section (dependencies, rbbuild, ...) - and any project keys this
    # controller doesn't model - untouched. Used both for save_file() and
    # by ConfigEditorView to build one whole-document preview out of each
    # section editor's own state.
    def patch_into_text(self, base_text: str) -> str:
        doc = tomlkit.parse(base_text) if base_text.strip() else tomlkit.document()
        values = self._collect_values()

        if not values and 'project' not in doc:
            return tomlkit.dumps(doc)

        project = doc.get('project')
        if project is None:
            strip_commented_placeholder(doc, 'project')
            project = tomlkit.table()
            doc['project'] = project

        for key in self._ALL_FIELDS:
            if key in values:
                project[key] = values[key]
            elif key in project:
                del project[key]

        if len(project) == 0:
            del doc['project']

        return tomlkit.dumps(doc)


    # Same TOML save_file() would write, without touching disk.
    def render_preview(self) -> str:
        return self.patch_into_text('')


    def save_file(self, path: Union[str, Path, None] = None):
        target = Path(path) if path else self.loaded_path
        if not target:
            raise ValueError('No file path to save to')

        try:
            with open(target, 'r', encoding='utf-8') as fd:
                text = fd.read()
        except FileNotFoundError:
            text = ''

        text = self.patch_into_text(text)
        with open(target, 'w', encoding='utf-8') as fd:
            fd.write(text)
        self.loaded_path = target
