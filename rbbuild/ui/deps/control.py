# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import tomlkit
from pathlib import Path
from typing import Dict, List, Optional, Union

from rbbuild.deps.parser import DepsParser
from rbbuild.deps.patcher import Patcher
from rbbuild.package.component_specifier import ComponentSpecifier
from rbbuild.package.package import Package, Supplier
from rbbuild.package.type import PackageType


# Business logic for the Deps Editor tab, bridging its view widgets with
# the shared active_deps document (a list of Package objects). Kept
# UI-framework-free so it can be unit tested directly, matching PkqController.
class DepsEditorController:

    # Section-level keys (apply to a whole [[dependencies]] section, as
    # opposed to a single entry) that the "Section settings" panel exposes
    # - see get_section_attrs()/apply_section_attrs(). Any other key
    # already present in a section (unlikely, but preserved regardless) is
    # left untouched.
    # 'no_traverse' is the legacy spelling of traverse=False; listing it
    # here makes saving through the panel drop it in favour of 'traverse'.
    _SECTION_FIELD_NAMES = (
        'namespace', 'installdir', 'restrict_platform', 'restrict_toolchain',
        'components', 'build_only', 'traverse', 'no_traverse',
        'package_install_action')

    def __init__(self, active_deps: List[Package], deps_parser: Optional[DepsParser] = None):
        self.active_deps = active_deps
        self.selected: Optional[Package] = None
        self.deps_parser = deps_parser
        self.loaded_path: Optional[Path] = None
        self._patcher = Patcher()
        self._section_attrs: List[dict] = []
        self._pkg_section: Dict[int, int] = {}
        self._entry_comments: Dict[int, dict] = {}
        self._section_trailing_comments: Dict[int, list] = {}
        self._table = 'dependencies'


    def select(self, index: int):
        if 0 <= index < len(self.active_deps):
            self.selected = self.active_deps[index]
        else:
            self.selected = None


    def remove_selected(self):
        if self.selected in self.active_deps:
            self.active_deps.remove(self.selected)
        self._pkg_section.pop(id(self.selected), None)
        self._entry_comments.pop(id(self.selected), None)
        self.selected = None


    # Index of the "current" section for the section-settings panel: the
    # selected entry's own section, or section 0 (created empty if none
    # exist yet) when nothing is selected - matches the common case of a
    # single [dependencies] section with no per-entry section switching UI.
    def current_section_index(self) -> int:
        if self.selected is not None and id(self.selected) in self._pkg_section:
            return self._pkg_section[id(self.selected)]
        if not self._section_attrs:
            self._section_attrs.append({})
        return 0


    def get_section_attrs(self) -> dict:
        return dict(self._section_attrs[self.current_section_index()])


    def apply_section_attrs(self, **fields):
        idx = self.current_section_index()
        attrs = dict(self._section_attrs[idx])
        for key in self._SECTION_FIELD_NAMES:
            value = fields.get(key)
            if key == 'traverse':
                keep = value is False
            else:
                keep = value not in (None, '', [], False)
            if keep:
                attrs[key] = value
            else:
                attrs.pop(key, None)
        self._section_attrs[idx] = attrs


    # Resets the editor to a fresh, empty document for target_filename's
    # format (rbbuild.toml/pyproject.toml decide which TOML table the
    # empty deps list is later saved under - see _table_for()). Clears
    # active_deps in place rather than reassigning it, since it's the
    # same list object shared with RBBuildGuiApp's sidebar.
    def new_document(self, target_filename: Union[str, Path]):
        self.active_deps.clear()
        self.selected = None
        self.loaded_path = None
        self._section_attrs = []
        self._pkg_section = {}
        self._entry_comments = {}
        self._section_trailing_comments = {}
        self._table = self._table_for(Path(target_filename))


    def apply_flags(
            self, build_only: bool, traverse: bool,
            components: str, suffixes: str):
        comps = self._split_csv(components)
        sufs = self._split_csv(suffixes)
        self.selected.component_specifier = ComponentSpecifier(
            components=comps, suffixes=sufs,
            build_only=build_only, traverse=traverse)


    def apply_sbom(
            self, cpe: str, copyright_: str, licenses: str,
            integration_type: str, component_type: str,
            supplier_name: str, supplier_email: str, supplier_url: str):
        pkg = self.selected
        pkg.cpe = cpe or None
        pkg.copyright = copyright_ or None
        # licenses is an SPDX expression string (e.g. "MIT OR Apache-2.0"),
        # not a comma list - License.coerce() only allows multiple licenses
        # per entry when none of them is a bare expression string.
        pkg.licenses = licenses or None
        pkg.integration_type = integration_type or None
        pkg.component_type = (
            PackageType.from_string(component_type) if component_type
            else PackageType.APPLICATION)

        if supplier_name or supplier_email or supplier_url:
            pkg.supplier = Supplier(
                name=supplier_name or None,
                email=supplier_email or None,
                url=supplier_url or None)
        else:
            pkg.supplier = None


    # Free-text note shown/edited above an entry - stored as its 'leading'
    # comment(s); any 'inline' comment read from the original file (see
    # open_file()) is left untouched since there's no UI for it.
    def get_comment(self, pkg: Package) -> str:
        return '\n'.join(self._entry_comments.get(id(pkg), {}).get('leading', []))


    def apply_comment(self, text: str):
        pkg = self.selected
        if pkg is None:
            return

        entry = dict(self._entry_comments.get(id(pkg), {}))
        lines = [line for line in (text or '').split('\n') if line.strip()]
        if lines:
            entry['leading'] = lines
        else:
            entry.pop('leading', None)

        if entry:
            self._entry_comments[id(pkg)] = entry
        else:
            self._entry_comments.pop(id(pkg), None)


    @staticmethod
    def _split_csv(value: str) -> Optional[list]:
        if not value:
            return None
        items = [item.strip() for item in value.split(',') if item.strip()]
        return items or None


    # Loads every [[dependencies]] section's entries into active_deps
    # (replacing its current contents) and remembers each entry's origin
    # section so save_file() can round-trip namespace/restrict_platform/
    # restrict_toolchain sections it has no UI for. Parses with tomlkit
    # (not tomllib) so each entry's comments can be recovered via
    # Patcher.read_array_comments() and carried forward on save.
    def open_file(self, path: Union[str, Path]):
        path = Path(path)
        with open(path, 'r', encoding='utf-8') as fd:
            text = fd.read()

        self._load_from_text(text, self._table_for(path))
        self.loaded_path = path


    # Re-parses arbitrary TOML text (e.g. a user-edited Preview pane) into
    # the model in place, same as open_file() - but doesn't touch
    # loaded_path, so Save still writes to wherever was previously opened/
    # chosen. table defaults to whatever open_file()/a prior call to this
    # method last established (see current_table()).
    def load_from_text(self, text: str, target_filename: Optional[str] = None):
        self._load_from_text(text, self.current_table(target_filename))


    # rbbuild.toml (and any other file) uses the bare [dependencies] table;
    # pyproject.toml nests it under [tool.rbbuild.dependencies] instead -
    # see _table_for(). Once a file is loaded, its own table is reused
    # regardless of target_filename/the dropdown, matching save_file().
    def current_table(self, target_filename: Optional[str] = None) -> str:
        if self.loaded_path is not None:
            return self._table
        return self._table_for(Path(target_filename or 'rbbuild.toml'))


    def _load_from_text(self, text: str, table: str):
        cfg = tomlkit.parse(text)
        dependencies_config = self._get_table(cfg, table)

        section_attrs = []
        pkg_section = {}
        entry_comments = {}
        section_trailing_comments = {}
        packages = []

        for idx, section in enumerate(dependencies_config):
            section_dict = section.unwrap()
            section_attrs.append({k: v for k, v in section_dict.items() if k != 'deps'})
            parse_attrs = self._section_parse_attrs(section_dict)
            deps_array = section.get('deps', [])
            array_comments = self._patcher.read_array_comments(deps_array)
            deps_items = section_dict.get('deps', [])
            for entry_idx, item in enumerate(deps_items):
                pkg = self.deps_parser.parse_item(item, parse_attrs)
                if pkg:
                    packages.append(pkg)
                    pkg_section[id(pkg)] = idx
                    if entry_idx in array_comments:
                        entry_comments[id(pkg)] = array_comments[entry_idx]

            trailing = array_comments.get(len(deps_items), {}).get('leading')
            if trailing:
                section_trailing_comments[idx] = trailing

        self._section_attrs = section_attrs
        self._pkg_section = pkg_section
        self._entry_comments = entry_comments
        self._section_trailing_comments = section_trailing_comments
        self._table = table
        self.selected = None
        self.active_deps.clear()
        self.active_deps.extend(packages)


    # pyproject.toml stores rbbuild's dependencies nested under
    # [tool.rbbuild.dependencies]; rbbuild.toml (and any other file) uses
    # the bare [dependencies] table - see documentation/user-manual/
    # rbbuild.toml.md and RBBuildConfiguration._load_pyproject_toml().
    @staticmethod
    def _table_for(path: Path) -> str:
        if path.name == 'pyproject.toml':
            return 'tool.rbbuild.dependencies'
        return 'dependencies'


    # Reads a (possibly dotted) table path out of a parsed TOML dict,
    # normalizing the single-table ([x]) and array-of-tables ([[x]]) forms
    # to always be a list, like Application.config.dependencies does.
    @staticmethod
    def _get_table(cfg: dict, table: str) -> list:
        node = cfg
        for part in table.split('.'):
            if not isinstance(node, dict) or part not in node:
                return []
            node = node[part]
        if isinstance(node, dict):
            return [node]
        return node if isinstance(node, list) else []


    # Mirrors DepsParser.walk()'s sec_attrs construction, minus the
    # restrict_platform/restrict_toolchain section-skipping - the editor
    # must show every entry regardless of the current platform/toolchain.
    def _section_parse_attrs(self, section: dict) -> dict:
        attrs = {}
        namespace = section.get('namespace', '')
        if namespace:
            attrs['installdir'] = namespace
            attrs['namespace'] = namespace

        skip = {'deps', 'namespace', 'restrict_platform', 'restrict_toolchain'}
        for key, value in section.items():
            if key in skip:
                continue
            attrs[key] = value if not isinstance(value, (bool, int, float)) else str(value)

        return attrs


    # Rewrites path (or the previously opened file, if path is None) in
    # place, preserving every section's other keys and any non-dependencies
    # content untouched (see Patcher). Entries added since the last
    # open_file() (e.g. via drag-and-drop from Package Query) are appended
    # to the first section, or placed in a new section if none exist yet.
    # If path doesn't refer to the file that was open()'d, the table to
    # write is re-derived from path's name (rbbuild.toml/pyproject.toml)
    # rather than reusing whatever was previously loaded.
    def save_file(self, path: Union[str, Path, None] = None):
        target = Path(path) if path else self.loaded_path
        if not target:
            raise ValueError('No file path to save to')

        table = self._table if target == self.loaded_path else self._table_for(target)
        self._patcher.update_dependencies_in_file(
            str(target), self._build_sections(), table,
            entry_comments=self._entry_comments)
        self.loaded_path = target
        self._table = table


    def _build_sections(self) -> List[dict]:
        by_section: Dict[int, List[Package]] = {i: [] for i in range(len(self._section_attrs))}
        unassigned = []
        for pkg in self.active_deps:
            idx = self._pkg_section.get(id(pkg))
            if idx in by_section:
                by_section[idx].append(pkg)
            else:
                unassigned.append(pkg)

        # A section with no attrs, no deps and no trailing comment (e.g.
        # the empty section current_section_index() creates as a side
        # effect of merely reading the Section settings panel) carries no
        # information worth writing out - skip it so an untouched document
        # doesn't grow a bare '[[dependencies]]\ndeps = []'.
        sections = []
        for i, attrs in enumerate(self._section_attrs):
            deps = by_section[i]
            if not attrs and not deps and i not in self._section_trailing_comments:
                continue
            section = dict(attrs)
            section['deps'] = deps
            if i in self._section_trailing_comments:
                section['_deps_trailing_comment'] = self._section_trailing_comments[i]
            sections.append(section)

        if unassigned:
            if sections:
                sections[0]['deps'] = sections[0]['deps'] + unassigned
            else:
                sections.append({'deps': unassigned})

        return sections


    # Same TOML save_file() would write, without touching disk.
    def render_preview(self, target_filename: Optional[str] = None) -> str:
        table = self.current_table(target_filename)
        return self._patcher.render_toml(
            self._build_sections(), table, entry_comments=self._entry_comments)


    # Folds the dependencies table into base_text, preserving every other
    # section (project, rbbuild, ...) untouched - used by ConfigEditorView
    # to build one whole-document preview out of each section editor's own
    # state, rather than each rendering its table in isolation.
    def patch_into_text(self, base_text: str, target_filename: Optional[str] = None) -> str:
        table = self.current_table(target_filename)
        return self._patcher.patch_dependencies_text(
            base_text, self._build_sections(), table,
            entry_comments=self._entry_comments)

