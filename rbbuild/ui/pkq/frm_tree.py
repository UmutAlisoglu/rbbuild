# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import webbrowser
from typing import List, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from rbbuild.core.runtime_settings import CompareState
from rbbuild.librbb.term import term
from rbbuild.package.diff import CompareResult
from rbbuild.package.package import Package
from rbbuild.service.issuetracker.issuetracker_manager import Issue
from rbbuild.service.repository.artifactory import Artifactory
from rbbuild.service.scm.bitbucket import Bitbucket
from rbbuild.service.scm.github import GitHub
from rbbuild.ui.pkq.control import PkqController


# Display names for the concrete service classes, keyed by type. Plugin
# repositories provide a 'display_name' class attribute instead.
_REPO_SERVICE_NAMES = {
    Artifactory: 'Artifactory',
}
_SCM_SERVICE_NAMES = {
    Bitbucket: 'Bitbucket',
    GitHub: 'GitHub',
}

# (color-kind, QColor) applied to a whole row for a given tag name.
_TAG_COLORS = {
    'filtered': ('fg', QColor('#d0d5d9')),
    'err':      ('bg', QColor('#ffb3b3')),
    'warn':     ('bg', QColor('#ffff99')),
    'same':     ('fg', QColor('#8e9aa4')),
    'deleted':  ('bg', QColor('#ffb3b3')),
    'moved':    ('bg', QColor('#ffff99')),
    'new':      ('bg', QColor('#9fe2bf')),
}


# QTreeWidget that also reports raw mouse press/move/release events, used to
# implement the manual drag-and-drop onto the Active Deps sidebar (see
# PkqPackagesTreeFrame._on_press/_on_drag_motion/_on_drag_release).
class _PackagesTreeWidget(QTreeWidget):

    def __init__(self, on_press, on_move, on_release, parent=None):
        super().__init__(parent)
        self._on_press = on_press
        self._on_move = on_move
        self._on_release = on_release


    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._on_press(event)


    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._on_move(event)


    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._on_release(event)


# Displays the resolved dependency tree, or, in diff mode, the nested
# "changes" (pkgA..pkgB) view, as a QTreeWidget.
class PkqPackagesTreeFrame:

    _MAX_COMPARE_VERSIONS = 30  # cap on entries shown directly in the 'Compare version' submenu

    _DEFAULT_ENABLED_STATES = frozenset({'changed', 'new', 'deleted'})

    _DRAG_THRESHOLD = 6  # pixels of motion before a press becomes a drag


    def __init__(self, parent, master: QWidget, controller: PkqController):
        self.master = master
        self.parent = parent
        self.controller = controller
        self._press_pos: Optional[QPoint] = None
        self._press_row: Optional[QTreeWidgetItem] = None
        self._drag: Optional[dict] = None  # {'pkg': Package, 'ghost': QLabel} once a drag is in progress
        self._frm = self._create_frm(master)


    @property
    def frm(self) -> QWidget:
        return self._frm


    def _create_frm(self, master: QWidget) -> QWidget:
        frm_tree = QWidget(master)
        layout = QVBoxLayout(frm_tree)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = _PackagesTreeWidget(self._on_press, self._on_drag_motion, self._on_drag_release)
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(['Name', 'Version', 'Toolchain', 'Attributes', 'Problems'])
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 140)
        self.tree.setColumnWidth(2, 160)
        self.tree.setColumnWidth(3, 200)
        self.tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_packages_menu)
        self.tree.itemSelectionChanged.connect(self.update_active_package)
        self.tree.itemDoubleClicked.connect(self.on_double_click)

        self._create_context_menu()

        layout.addWidget(self.tree)
        return frm_tree


    def update_active_package(self):
        selected = self.tree.selectedItems()
        idx = selected[0].data(0, Qt.UserRole) if selected else None
        if idx is None:
            self.parent.clear_properties()
            return

        term.debug(f'Selected package idx: {idx}')
        self.controller.set_package(idx)
        self.parent.update_properties()


    # Selects/focuses the first top-level row after a query, so the
    # properties panel is populated without requiring a manual click.
    def select_top(self):
        if self.tree.topLevelItemCount() == 0:
            return

        top = self.tree.topLevelItem(0)
        self.tree.setCurrentItem(top)
        self.update_active_package()


    def invalidate_packages(self):
        self.tree.clear()
        self.tree.addTopLevelItem(QTreeWidgetItem(['<no package found>']))
        self.parent.clear_properties()


    # Dispatches to display_tree() or display_changes_list() (diff mode).
    def display_packages(self, txt_filter: str = '', collapse: bool = False, filter_problems: bool = False, enabled_states: Optional[set] = None):
        self.tree.clear()
        if not self.controller.diff_mode:
            self.display_tree(txt_filter, collapse, filter_problems)
        else:
            self.display_changes_list(enabled_states)


    def display_tree(self, txt_filter: str, collapse: bool, filter_problems: bool):
        entries = self.controller.entries
        if not entries:
            return

        self.begin_streaming(txt_filter, collapse, filter_problems)
        for pkg, depth in entries:
            self.append_entry(pkg, depth)
        self._set_normal_columns_visible(self._stream_has_problems)


    # Resets incremental-insert state before a sequence of append_entry() calls.
    def begin_streaming(self, txt_filter: str = '', collapse: bool = False, filter_problems: bool = False):
        self.tree.clear()
        self._stream_filter = txt_filter
        self._stream_collapse = collapse
        self._stream_filter_problems = filter_problems
        self._stream_idx = [[]]  # per-depth list of last-inserted items
        self._stream_has_problems = False
        self._stream_count = 0


    # Inserts a single (pkg, depth) row, using the filter/collapse/problems
    # settings captured by the most recent begin_streaming() call.
    def append_entry(self, pkg: Package, depth: int):
        idx = self._stream_idx
        while len(idx) <= depth:
            idx.append([])

        idx_open_parent = not self._stream_collapse
        tags = []
        # TODO: filter only matches the combined name-version string, not per-column.
        # An empty filter matches everything, so it must not force ancestors
        # open by itself - only a genuine (non-empty) filter match does.
        if self._stream_filter and self._stream_filter not in str(pkg):
            tags.append('filtered')
        elif self._stream_filter and self._stream_collapse:
            idx_open_parent = True

        comment = ''
        if self.controller.is_conflicted(pkg):
            tags.append('err')
            comment = self.controller.conflict_message(pkg) or ''
            self._stream_has_problems = True
            if self._stream_collapse and self._stream_filter_problems:
                idx_open_parent = True

        item = QTreeWidgetItem([
            pkg.name or '',
            pkg.version or '',
            str(pkg.toolchain) if pkg.toolchain else '',
            self._package_attrs(pkg),
            comment,
        ])
        item.setData(0, Qt.UserRole, self._stream_count)
        self._apply_row_colors(item, tags)

        if depth == 0:
            self.tree.addTopLevelItem(item)
        else:
            idx[depth - 1][-1].addChild(item)
        item.setExpanded(not self._stream_collapse)

        idx[depth].append(item)
        self._stream_count += 1

        if self._stream_collapse and idx_open_parent:
            for d in range(depth, 0, -1):
                idx[d - 1][-1].setExpanded(True)


    def _apply_row_colors(self, item: QTreeWidgetItem, tags: List[str]):
        for tag in tags:
            kind, color = _TAG_COLORS.get(tag, (None, None))
            if kind is None:
                continue
            for col in range(self.tree.columnCount()):
                if kind == 'bg':
                    item.setBackground(col, color)
                else:
                    item.setForeground(col, color)


    def _set_normal_columns_visible(self, has_problems: bool):
        for col in (1, 2, 3):
            self.tree.setColumnHidden(col, False)
        self.tree.setColumnHidden(4, not has_problems)


    def _set_diff_columns_visible(self):
        for col in (1, 2, 4):
            self.tree.setColumnHidden(col, True)
        self.tree.setColumnHidden(3, False)


    # Attribute summary shown in the "Attributes" column.
    def _package_attrs(self, pkg: Package) -> str:
        if not pkg.manifest_loaded:
            return ''

        attrs = []
        if pkg.namespace:
            attrs.append(pkg.namespace)
        if pkg.build_only:
            attrs.append('build_only')
        if not pkg.traverse:
            attrs.append('traverse=0')
        return '_'.join(attrs)


    # Renders the flat (CompareResult, depth) list from the controller as a nested tree.
    def display_changes_list(self, enabled_states: Optional[set] = None):
        entries = self.controller.cmp_entries
        if not entries:
            return

        self.begin_streaming_compare(enabled_states)
        for cmp_res, depth in entries:
            self.append_compare_entry(cmp_res, depth)
        self._set_diff_columns_visible()


    # Like begin_streaming(), but for diff mode.
    def begin_streaming_compare(self, enabled_states: Optional[set] = None):
        self.tree.clear()
        self._stream_enabled_states = enabled_states if enabled_states is not None else self._DEFAULT_ENABLED_STATES
        self._stream_last_visible = {}  # depth -> item of the last inserted (visible) row at that depth
        self._stream_count = 0


    # Inserts a (cmp_res, depth) row; disabled-state entries are skipped
    # entirely, and their visible descendants get reparented onto the
    # nearest visible ancestor instead of being dropped too.
    def append_compare_entry(self, cmp_res: CompareResult, depth: int):
        last_visible = self._stream_last_visible
        for stale_depth in [d for d in last_visible if d >= depth]:
            del last_visible[stale_depth]

        tag = cmp_res.state.name.lower()  # 'same' | 'changed' | 'new' | 'deleted' | 'moved'
        state_filter_tag = 'changed' if tag == 'moved' else tag
        if state_filter_tag not in self._stream_enabled_states:
            return

        title = self._compare_title(cmp_res)
        parent_item = None
        for ancestor_depth in range(depth - 1, -1, -1):
            if ancestor_depth in last_visible:
                parent_item = last_visible[ancestor_depth]
                break

        item = QTreeWidgetItem([title, '', '', tag, ''])
        item.setData(0, Qt.UserRole, self._stream_count)
        self._apply_row_colors(item, [tag])

        if parent_item is None:
            self.tree.addTopLevelItem(item)
        else:
            parent_item.addChild(item)
        item.setExpanded(True)

        last_visible[depth] = item
        self._stream_count += 1


    # Builds the display title for one CompareResult.
    def _compare_title(self, cmp_res: CompareResult) -> str:
        pkg = cmp_res.pkg_b or cmp_res.pkg_a
        namespace = (pkg.namespace + '/') if pkg and pkg.namespace else ''

        if cmp_res.state == CompareState.CHANGED:
            return f'{namespace}{cmp_res.pkg_a} .. {cmp_res.pkg_b}'
        if cmp_res.state == CompareState.MOVED:
            return f'{namespace}{cmp_res.pkg_b}'
        return str(pkg) if pkg else ''


    def _create_context_menu(self):
        self._menu = QMenu(self.tree)
        self._act_copy = self._menu.addAction('Copy', self.copy_package_string)
        self._menu.addSeparator()
        self._act_open_repo = self._menu.addAction('Open in Artifactory', self.open_artifactory)
        self._act_open_scm = self._menu.addAction('Open in Bitbucket', lambda: self.open_bitbucket())
        self._act_open_scm_prev = self._menu.addAction('Open in Bitbucket (previous)', lambda: self.open_bitbucket('prev'))
        self._act_open_scm_diff = self._menu.addAction('Open in Bitbucket (diff)', lambda: self.open_bitbucket('diff'))
        self._act_open_jira = self._menu.addAction('Open in JIRA', self.open_jira)
        self._act_open_jenkins = self._menu.addAction('Open in Jenkins', self.open_jenkins)
        self._menu.addSeparator()
        self._act_browse = self._menu.addAction('Browse this package', self.browse_package)
        self._menu.addAction('Add to deps list', self.add_to_deps_list)
        self.compare_menu = QMenu('Compare version', self._menu)
        self._menu.addMenu(self.compare_menu)


    def show_packages_menu(self, pos):
        if not self.controller.package:
            return
        self._reconfigure_packages_menu()
        self._menu.exec(self.tree.viewport().mapToGlobal(pos))


    def _reconfigure_packages_menu(self):
        has_git = self._has_git
        has_prev = self._has_prev
        repo_name = self._repo_display_name()
        scm_name = self._scm_display_name()

        self._act_open_repo.setText(f'Open in {repo_name}')
        self._act_open_scm.setText(f'Open in {scm_name}')
        self._act_open_scm.setEnabled(has_git)
        self._act_open_scm_prev.setText(f'Open in {scm_name} (previous)')
        self._act_open_scm_prev.setEnabled(has_prev)
        self._act_open_scm_diff.setText(f'Open in {scm_name} (diff)')
        self._act_open_scm_diff.setEnabled(has_prev)
        self._act_open_jenkins.setEnabled(self._has_build_url)
        self._act_open_jira.setEnabled(bool(self._jira_key()))
        self._act_browse.setEnabled(not self._is_current_root)
        self._reconfigure_compare_menu()


    # Repopulates the 'Compare version' submenu: a single 'Compare <old> and
    # <new>' command if 2+ rows are selected, otherwise the cascade listing
    # other versions of the selected package, paginated via 'More
    # versions...' (see _fill_compare_menu()).
    def _reconfigure_compare_menu(self):
        self.compare_menu.clear()
        oldest, newest = self._oldest_newest_selected()

        if oldest and newest:
            label = f'Compare {oldest.version} and {newest.version}'
            self.compare_menu.addAction(label, lambda: self.compare_selected(oldest, newest))
            self.compare_menu.setEnabled(True)
            return

        pkg = self.controller.package
        versions = self.controller.other_versions(pkg) if pkg else []
        baseline_version = (pkg.version if pkg else None) or (versions[0] if versions else None)

        self._fill_compare_menu(self.compare_menu, versions, baseline_version)
        self.compare_menu.setEnabled(bool(versions))


    # Fills menu with up to _MAX_COMPARE_VERSIONS entries; if more remain,
    # recurses into a nested 'More versions...' submenu.
    def _fill_compare_menu(self, menu: QMenu, versions: List[str], baseline_version: Optional[str]):
        batch, rest = versions[:self._MAX_COMPARE_VERSIONS], versions[self._MAX_COMPARE_VERSIONS:]

        for version in batch:
            menu.addAction(version, lambda v=version, b=baseline_version: self.compare_version(v, b))

        if not rest:
            return

        submenu = QMenu('More versions...', menu)
        menu.addSeparator()
        menu.addMenu(submenu)
        self._fill_compare_menu(submenu, rest, baseline_version)


    # Oldest/newest selected Package (entries are already sorted newest to
    # oldest). Returns (None, None) if fewer than two selected rows share a
    # common, versioned package name.
    def _oldest_newest_selected(self):
        entries = self.controller.entries
        indices = sorted(
            idx for idx in (item.data(0, Qt.UserRole) for item in self.tree.selectedItems())
            if idx is not None)

        packages = []
        for idx in indices:
            if 0 <= idx < len(entries):
                pkg, _ = entries[idx]
                if pkg.version:
                    packages.append(pkg)

        if len(packages) < 2 or len({pkg.name for pkg in packages}) != 1:
            return None, None

        return packages[-1], packages[0]


    # Initiates a version-range diff query between two selected packages.
    def compare_selected(self, pkg_old: Package, pkg_new: Package):
        self.parent.navigate_to_compare(pkg_old.name, pkg_old.version, pkg_new.version)


    @property
    def _has_git(self) -> bool:
        pkg = self.controller.package
        return bool(pkg and pkg.git_repo)


    @property
    def _has_build_url(self) -> bool:
        pkg = self.controller.package
        return bool(pkg and pkg.build_url)


    @property
    def _has_prev(self) -> bool:
        return self.controller.diff_mode and self.controller.package_prev is not None


    # True if the selected package is already the one being displayed.
    @property
    def _is_current_root(self) -> bool:
        pkg = self.controller.package
        root = self.controller.current_root_package
        return bool(pkg and root and pkg == root)


    # Jira ticket key abbreviated from the package's branch, e.g. 'PROJECT-1234'.
    def _jira_key(self) -> Optional[str]:
        pkg = self.controller.package
        if not pkg or not pkg.branch:
            return None
        return Issue.branch_abbreviated(pkg.branch)


    # Display name of the repository service, e.g. 'Artifactory' - falls back to 'Repository'.
    def _repo_display_name(self) -> str:
        pkg = self.controller.package
        if not pkg or not pkg.channel:
            return 'Repository'
        try:
            service = self.controller.repoman.service(channel=pkg.channel)
        except Exception:
            return 'Repository'
        return _REPO_SERVICE_NAMES.get(type(service)) or getattr(service, 'display_name', 'Repository')


    # Display name of the git hosting service, e.g. 'Bitbucket' - falls back to 'Git'.
    def _scm_display_name(self) -> str:
        pkg = self.controller.package
        if not pkg or not pkg.git_repo:
            return 'Git'
        try:
            service = self.controller.scmman.service(url=pkg.git_repo)
        except Exception:
            return 'Git'
        return _SCM_SERVICE_NAMES.get(type(service), 'Git')


    def copy_package_string(self):
        QApplication.clipboard().setText(str(self.controller.package))


    # Double-click is a shortcut for 'Browse this package'.
    def on_double_click(self, item: QTreeWidgetItem, column: int):
        if not self.controller.package or self._is_current_root:
            return
        self.browse_package()


    def browse_package(self):
        self.parent.navigate_to_package_exact(self.controller.package)


    def add_to_deps_list(self):
        pkg = self.controller.package
        if pkg:
            self.parent.add_to_deps(pkg)


    def _package_for_row(self, item: Optional[QTreeWidgetItem]) -> Optional[Package]:
        if item is None:
            return None
        idx = item.data(0, Qt.UserRole)
        if idx is None:
            return None
        entries = self.controller.entries
        return entries[idx][0] if 0 <= idx < len(entries) else None


    def _on_press(self, event):
        pos = event.position().toPoint()
        item = self.tree.itemAt(pos)
        self._press_pos = event.globalPosition().toPoint() if item is not None else None
        self._press_row = item


    # Once the press has moved far enough, starts a drag: creates a small
    # floating ghost label following the cursor, dropped in _on_drag_release().
    def _on_drag_motion(self, event):
        if self._press_pos is None:
            return

        global_pos = event.globalPosition().toPoint()
        if self._drag is None:
            dx = global_pos.x() - self._press_pos.x()
            dy = global_pos.y() - self._press_pos.y()
            if max(abs(dx), abs(dy)) < self._DRAG_THRESHOLD:
                return
            pkg = self._package_for_row(self._press_row)
            if pkg is None:
                return
            self._drag = {'pkg': pkg, 'ghost': self._create_ghost(pkg)}

        self._drag['ghost'].move(global_pos + QPoint(12, 8))


    def _create_ghost(self, pkg: Package) -> QLabel:
        ghost = QLabel(str(pkg))
        ghost.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
        ghost.setStyleSheet('background-color: #ffffe0; border: 1px solid black; padding: 4px;')
        ghost.show()
        return ghost


    def _on_drag_release(self, event):
        self._press_pos = None
        if self._drag is None:
            return

        pkg = self._drag['pkg']
        self._drag['ghost'].close()
        self._drag = None

        global_pos = event.globalPosition().toPoint()
        target = QApplication.widgetAt(global_pos)
        if self.parent.is_deps_drop_target(target):
            self.parent.add_to_deps(pkg)


    # 'Compare version' submenu handler - diffs baseline_version against the chosen one.
    def compare_version(self, version: str, baseline_version: str):
        pkg = self.controller.package
        if not pkg or not baseline_version:
            return
        self.parent.navigate_to_compare(pkg.name, baseline_version, version)


    def open_url(self, url: str):
        term.info(f'Opening URL: {url}')
        webbrowser.open(url)


    def open_artifactory(self):
        pkg = self.controller.package
        if not pkg or not pkg.url:
            term.warning(f'{pkg} has no URL entry!')
            return

        url = pkg.url
        # Compensate bug in manifests which were written before the issue was fixed.
        # The URL in these manifests begins with 'http://https://'. We have to strip away http://
        if url.startswith('http://https://'):
            url = url[len('http://'):]
        self.open_url(url)


    def open_bitbucket(self, mode: str = None):
        pkg = self.controller.package
        if not pkg or not pkg.git_repo:
            return

        try:
            git_service = self.controller.scmman.service(url=pkg.git_repo)
        except Exception as e:
            term.warning('SCM lookup failed', str(e))
            return

        if not mode:
            url = git_service.commit_url(pkg.git_hash)
        elif mode in ('prev', 'diff'):
            pkg_prev = self.controller.package_prev
            if not pkg_prev or not pkg_prev.git_hash:
                return
            url = git_service.commit_url(pkg_prev.git_hash) if mode == 'prev' else git_service.compare_url(pkg_prev.git_hash, pkg.git_hash)
        else:
            return

        self.open_url(url)


    def open_jira(self):
        jira_key = self._jira_key()
        if not jira_key:
            return

        jira_id = jira_key.split('-')[0]
        try:
            jira_service = self.controller.issueman.service(jira_id)
        except Exception as e:
            term.warning('JIRA lookup failed', str(e))
            return
        self.open_url(f'{jira_service.url}browse/{jira_key}')


    def open_jenkins(self):
        pkg = self.controller.package
        if not pkg or not pkg.build_url:
            return

        self.open_url(pkg.build_url)
