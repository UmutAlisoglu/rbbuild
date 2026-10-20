# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Dict, List, Optional

import tomlkit
from tomlkit.items import Comment, Null, Whitespace

from rbbuild.deps.serializer import Serializer
from rbbuild.package.package import Package
from rbbuild.toml_template import strip_commented_placeholder


# Rewrites only the dependencies table(s) of a TOML file - 'dependencies'/
# '[[dependencies]]' for rbbuild.toml, or 'tool.rbbuild.dependencies'/
# '[[tool.rbbuild.dependencies]]' for pyproject.toml - leaving everything
# else, including comments anywhere in the file (even inside the
# dependencies array itself), untouched. Creates the file if it doesn't
# exist yet. Built on tomlkit (rather than text-splicing) so comments
# genuinely round-trip through open/edit/save.
class Patcher:

    def __init__(self):
        self._serializer = Serializer()


    # entry_comments maps id(pkg) (for Package entries in
    # dependencies_config) to {'leading': [str, ...], 'inline': str} - see
    # read_array_comments() and DepsEditorController, the only source of
    # comments to restore (a freshly assembled dependencies_config has
    # none).
    def update_dependencies_in_file(
            self, path: str, dependencies_config: list,
            table: str = 'dependencies', entry_comments: Optional[dict] = None):
        try:
            with open(path, 'r', encoding='utf-8') as fd:
                text = fd.read()
        except FileNotFoundError:
            text = ''

        text = self.patch_dependencies_text(
            text, dependencies_config, table, entry_comments)

        with open(path, 'w', encoding='utf-8') as fd:
            fd.write(text)


    # Same as update_dependencies_in_file(), but operates purely on TOML
    # text - no file I/O. Used to fold the dependencies table into a
    # shared whole-document text (see ConfigEditorView), where each
    # section's editor patches its own table into the same growing text in
    # turn, rather than each one owning its own file read/write.
    def patch_dependencies_text(
            self, text: str, dependencies_config: list,
            table: str = 'dependencies', entry_comments: Optional[dict] = None) -> str:
        doc = tomlkit.parse(text) if text.strip() else tomlkit.document()
        self._write_table(doc, table, dependencies_config, entry_comments)
        return tomlkit.dumps(doc)


    # Renders dependencies_config as standalone TOML text, without reading
    # or writing any file - used for the Deps Editor's live preview, so it
    # can show the same comments update_dependencies_in_file() would write.
    def render_toml(
            self, dependencies_config: list, table: str = 'dependencies',
            entry_comments: Optional[dict] = None) -> str:
        doc = tomlkit.document()
        self._write_table(doc, table, dependencies_config, entry_comments)
        return tomlkit.dumps(doc)


    def _write_table(self, doc, table, dependencies_config, entry_comments):
        parts = table.split('.')
        container = doc
        for part in parts[:-1]:
            if part not in container:
                strip_commented_placeholder(doc, part)
                container[part] = tomlkit.table(is_super_table=True)
            container = container[part]

        aot = self._build_aot(dependencies_config, entry_comments or {})
        if len(aot):
            if parts[-1] not in container:
                strip_commented_placeholder(doc, parts[-1])
            container[parts[-1]] = aot
        elif parts[-1] in container:
            del container[parts[-1]]


    def _build_aot(self, dependencies_config: list, entry_comments: dict):
        aot = tomlkit.aot()
        for section in dependencies_config:
            tbl = tomlkit.table()
            for key, value in section.items():
                if key not in ('deps', '_deps_trailing_comment'):
                    tbl[key] = value
            tbl['deps'] = self._build_deps_array(
                section.get('deps', []), entry_comments,
                section.get('_deps_trailing_comment'))
            aot.append(tbl)
        return aot


    def _build_deps_array(
            self, deps: list, entry_comments: dict,
            trailing_comment: Optional[list] = None):
        arr = tomlkit.array()
        arr.multiline(True)
        for item in deps:
            comments = {}
            if isinstance(item, Package):
                comments = entry_comments.get(id(item), {})
                item = self._serializer.package_to_deps_item(item)
            for leading in comments.get('leading', []):
                arr.add_line(comment=leading)
            arr.add_line(
                self._to_tomlkit_value(item), comment=comments.get('inline'))
        for leading in (trailing_comment or []):
            arr.add_line(comment=leading)
        if deps or trailing_comment:
            arr.add_line(indent='')
        return arr


    @staticmethod
    def _to_tomlkit_value(value):
        if isinstance(value, dict):
            table = tomlkit.inline_table()
            for key, val in value.items():
                table[key] = Patcher._to_tomlkit_value(val)
            return table
        if isinstance(value, list):
            return [Patcher._to_tomlkit_value(v) for v in value]
        return value


    # Reads the leading/inline comments attached to each entry of a
    # just-parsed deps array, keyed by the entry's 0-based position in the
    # array - relies on Array's internal item grouping (._value), since
    # tomlkit has no public per-item trivia accessor for arrays. A trailing
    # comment with no following entry (e.g. a fully commented-out example
    # left in an otherwise-empty array) is returned under the key equal to
    # the array's length - see _build_deps_array()'s trailing_comment.
    @staticmethod
    def read_array_comments(array) -> Dict[int, dict]:
        body = getattr(array, '_value', None)
        if body is None:
            return {}

        comments: Dict[int, dict] = {}
        pending_leading: List[str] = []
        index = 0
        for group in body:
            value_item = None
            comment_item = None
            for element in group:
                if isinstance(element, Comment):
                    comment_item = element
                elif not isinstance(element, (Whitespace, Null)):
                    value_item = element

            if value_item is None:
                if comment_item is not None:
                    pending_leading.append(
                        comment_item.trivia.comment.lstrip('#').strip())
                continue

            entry = {}
            if pending_leading:
                entry['leading'] = pending_leading
                pending_leading = []
            if comment_item is not None:
                entry['inline'] = comment_item.trivia.comment.lstrip('#').strip()
            if entry:
                comments[index] = entry
            index += 1

        if pending_leading:
            comments[index] = {'leading': pending_leading}

        return comments
