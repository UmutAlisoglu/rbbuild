# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import tomlkit
from pathlib import Path
from typing import List, Optional, Union

from rbbuild.toml_template import strip_commented_placeholder


# Business logic for the "rbbuild" sub-tab of the rbbuild.toml editor,
# covering the [rbbuild] table (bare rbbuild.toml) / [tool.rbbuild] table
# (pyproject.toml, alongside [tool.rbbuild.dependencies],
# [tool.rbbuild.packaging], etc. - only the actions/build-tools/
# documentation-tools/test-tools/sca-tools keys belong to this controller; every other key
# under [tool.rbbuild] is left untouched). Kept UI-framework-free so it
# can be unit tested directly, matching DepsEditorController/ProjectController.
class RbbuildSettingsController:

    _FIELDS = ('actions', 'build_tools', 'documentation_tools', 'test_tools', 'sca_tools')

    def __init__(self):
        self.loaded_path: Optional[Path] = None
        self.new_document()


    def new_document(self):
        self.actions: List[str] = []
        self.build_tools: List[str] = []
        self.documentation_tools: List[str] = []
        self.test_tools: List[str] = []
        self.sca_tools: List[str] = []
        self.loaded_path = None


    def open_file(self, path: Union[str, Path]):
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as fd:
            text = fd.read()

        self._load_from_text(text, self._table_for(path))
        self.loaded_path = path


    # Re-parses arbitrary TOML text (e.g. a user-edited whole-document
    # preview) into the model in place - same as open_file(), but doesn't
    # touch loaded_path.
    def load_from_text(self, text: str, target_filename: Optional[str] = None):
        self._load_from_text(text, self.current_table(target_filename))


    def _load_from_text(self, text: str, table: str):
        doc = tomlkit.parse(text) if text.strip() else tomlkit.document()
        section = self._get_table(doc, table)

        for key in self._FIELDS:
            setattr(self, key, list(section.get(self._toml_key(key), section.get(key, []))))


    # rbbuild.toml uses the bare [rbbuild] table; pyproject.toml nests it
    # as [tool.rbbuild] alongside dependencies/packaging/oss/etc - see
    # documentation/user-manual/rbbuild.toml.md.
    @staticmethod
    def _table_for(path: Path) -> str:
        if path.name == 'pyproject.toml':
            return 'tool.rbbuild'
        return 'rbbuild'


    # Which table current edits belong to: the table of whichever file
    # was last opened, or target_filename's format if none has been -
    # mirrors DepsEditorController.current_table().
    def current_table(self, target_filename: Optional[str] = None) -> str:
        if self.loaded_path is not None:
            return self._table_for(self.loaded_path)
        return self._table_for(Path(target_filename or 'rbbuild.toml'))


    @staticmethod
    def _get_table(doc, table: str) -> dict:
        node = doc
        for part in table.split('.'):
            if part not in node:
                return {}
            node = node[part]
        return node


    # The canonical key spelling in TOML files uses hyphens; the underscore
    # spelling is still read.
    @staticmethod
    def _toml_key(field: str) -> str:
        return field.replace('_', '-')


    def _collect_values(self) -> dict:
        return {key: getattr(self, key) for key in self._FIELDS if getattr(self, key)}


    # Folds the fields into base_text's
    # [rbbuild] (or [tool.rbbuild]) table, preserving every other section
    # and every other key already in that table (dependencies, packaging,
    # ... for [tool.rbbuild]) untouched.
    def patch_into_text(self, base_text: str, target_filename: Optional[str] = None) -> str:
        return self._patch_table(base_text, self.current_table(target_filename))


    def _patch_table(self, base_text: str, table: str) -> str:
        doc = tomlkit.parse(base_text) if base_text.strip() else tomlkit.document()
        values = self._collect_values()

        node = doc
        for part in table.split('.'):
            if part not in node:
                if not values:
                    return tomlkit.dumps(doc)
                strip_commented_placeholder(doc, part)
                node[part] = tomlkit.table()
            node = node[part]

        for key in self._FIELDS:
            toml_key = self._toml_key(key)
            if toml_key != key and key in node:
                del node[key]
            if key in values:
                node[toml_key] = values[key]
            elif toml_key in node:
                del node[toml_key]

        if len(node) == 0:
            parent = doc
            parts = table.split('.')
            for part in parts[:-1]:
                parent = parent[part]
            del parent[parts[-1]]

        return tomlkit.dumps(doc)


    # Same TOML save_file() would write, without touching disk.
    def render_preview(self, target_filename: Optional[str] = None) -> str:
        return self.patch_into_text('', target_filename)


    # table is derived from target itself (not the previously loaded
    # path), so saving under a new filename - e.g. "Save As" switching
    # rbbuild.toml <-> pyproject.toml - picks up the new table correctly.
    def save_file(self, path: Union[str, Path, None] = None):
        target = Path(path) if path else self.loaded_path
        if not target:
            raise ValueError('No file path to save to')

        try:
            with open(target, 'r', encoding='utf-8') as fd:
                text = fd.read()
        except FileNotFoundError:
            text = ''

        text = self._patch_table(text, self._table_for(target))
        with open(target, 'w', encoding='utf-8') as fd:
            fd.write(text)
        self.loaded_path = target
