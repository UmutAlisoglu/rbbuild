# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Callable, NamedTuple, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from rbbuild.container.application import Application
from rbbuild.librbb.term import term
from rbbuild.package.package import Package
from rbbuild.ui.async_task import AsyncTaskQueue
from rbbuild.ui.pkq.control import PkqController
from rbbuild.ui.pkq.frm_filter import PkqFilterFrame
from rbbuild.ui.pkq.frm_properties import PkqPropertiesFrame
from rbbuild.ui.pkq.frm_query import PkqQueryFrame
from rbbuild.ui.pkq.frm_tree import PkqPackagesTreeFrame


# A single back/forward history entry: the query text plus the channel and
# toolchain that were selected when it was queried - re-issuing the query
# text alone is not enough, since the same text can resolve differently
# depending on the active channel/toolchain (see PkqView._capture_nav_state).
class _NavState(NamedTuple):
    query_text: str
    channel: Optional[str]
    toolchain: Optional[str]


# Top-level content widget for the pkq (package query) tool. Composes the
# query bar, results tree, filter bar and properties panel, all backed by a
# single PkqController. on_profile_change is called with the newly picked
# profile name (see "Switching profile" in
# documentation/developer-manual/gui_architecture.md); active_deps/
# on_active_deps_change/deps_drop_target wire up "Add to deps list" and
# drag-and-drop in PkqPackagesTreeFrame (see add_to_deps() below).
class PkqView(QWidget):

    def __init__(self, master: QWidget, application: Application, args, on_profile_change: Optional[Callable[[str], None]] = None, restore_history: bool = True,
                 active_deps: Optional[list] = None, on_active_deps_change: Optional[Callable[[], None]] = None, deps_drop_target: Optional[QWidget] = None):
        super().__init__(master)
        self.controller = PkqController(application, args)
        self.on_profile_change = on_profile_change
        self.active_deps = active_deps if active_deps is not None else []
        self.on_active_deps_change = on_active_deps_change
        self.deps_drop_target = deps_drop_target
        self._query_queue = AsyncTaskQueue(self)
        self._history: list[_NavState] = []
        self._forward: list[_NavState] = []
        self._streaming_started = False
        self._busy = False

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        content_layout = QHBoxLayout()
        outer_layout.addLayout(content_layout, 1)

        self.frame_left = QWidget()
        left_layout = QVBoxLayout(self.frame_left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.frame_left, 1)

        self._query_frame = PkqQueryFrame(self, self.frame_left, self.controller)
        left_layout.addWidget(self._query_frame.frm)

        self._tree_frame = PkqPackagesTreeFrame(self, self.frame_left, self.controller)
        left_layout.addWidget(self._tree_frame.frm, 1)

        self._filter_frame = PkqFilterFrame(self, self.frame_left)
        left_layout.addWidget(self._filter_frame.frm)

        self._properties_frame = PkqPropertiesFrame(self, self, self.controller)
        content_layout.addWidget(self._properties_frame.frm)
        self._properties_frame.hide()

        self.status_frame = QWidget()
        outer_layout.addWidget(self.status_frame)
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(5, 2, 5, 2)

        self.status_label = QLabel('')
        status_layout.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(150)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        status_layout.addWidget(self.progress_bar)

        initial_package = getattr(args, 'package', None)
        last_entry = self.controller.history.last() if restore_history else None
        if initial_package:
            self._query_frame.txt = initial_package
        elif last_entry and last_entry.get('package'):
            self._query_frame.txt = last_entry['package']

        # History isn't scoped per profile, so a channel/toolchain restored
        # from a previous profile may not exist in this one (e.g. right
        # after a profile switch) - only restore it if it's still valid here.
        if (not getattr(args, 'channel', None) and last_entry and last_entry.get('channel')
                and last_entry['channel'] in self.controller.channels):
            self.controller.select_channel(last_entry['channel'])
            self._query_frame.update_channels()

        if (not getattr(args, 'tcid', None) and last_entry and last_entry.get('toolchain')
                and last_entry['toolchain'] in self.controller.toolchains):
            self.controller.select_platform_toolchain(last_entry['toolchain'])
            self._query_frame.update_toolchains()

        self.query()


    # Runs on a background thread via self._query_queue so the Qt event loop
    # never blocks. Results stream into the tree as they're found (see
    # _on_query_progress()).
    #
    # record_history is False for go_back()/go_forward(), so re-visiting a
    # query doesn't re-promote it in the persistent recent-queries list -
    # only genuinely new navigations should do that.
    def query(self, event=None, *, text: str = None, pkg: Package = None, record_history: bool = True):
        if pkg is not None:
            self._query_frame.txt = self._display_text(pkg)
        elif text is not None:
            self._query_frame.txt = text
        else:
            text = self._query_frame.txt

        self.status_busy('Querying ...')
        self._streaming_started = False
        self._progress_count = 0

        def work(report_progress):
            return self.controller.query(text=text, pkg=pkg, report_progress=report_progress)

        def on_success(ok):
            if not ok:
                self._tree_frame.invalidate_packages()
            else:
                self.display_packages()
                self._tree_frame.select_top()
                if record_history:
                    self.controller.history.add(
                        self._query_frame.txt,
                        channel=str(self.controller.channel) if self.controller.channel else None,
                        toolchain=str(self.controller.toolchain) if self.controller.toolchain else None,
                    )
            self.status_ready()

        def on_error(exc):
            term.error('failed', exc)
            self._tree_frame.invalidate_packages()
            self.status_ready()

        self._query_queue.submit(work, on_success, on_error, on_progress=self._on_query_progress)


    # Captures the query text plus the currently selected channel/toolchain,
    # so a later go_back()/go_forward() can restore the exact context a
    # history entry was queried under, not just its text.
    def _capture_nav_state(self) -> _NavState:
        channel = self.controller.channel
        toolchain = self.controller.toolchain
        return _NavState(
            query_text=self._query_frame.txt,
            channel=str(channel) if channel else None,
            toolchain=str(toolchain) if toolchain else None,
        )


    # Restores the channel/toolchain overrides (and dropdown widgets) from a
    # history entry, before re-issuing its query.
    def _restore_nav_state(self, state: _NavState):
        if state.channel:
            self.controller.select_channel(state.channel)
        if state.toolchain:
            self.controller.select_platform_toolchain(state.toolchain)
        self._query_frame.update_channels()
        self._query_frame.update_toolchains()


    # Syncs the channel/toolchain dropdowns (and underlying controller
    # overrides) to an exact Package's own channel/toolchain before
    # resolving it - otherwise the dropdowns keep showing whatever was
    # selected before, and a later go_back() would re-resolve this entry
    # under the wrong toolchain (see navigate_to_package_exact()).
    def _apply_package_context(self, pkg: Package):
        if pkg.channel:
            self.controller.select_channel(str(pkg.channel))
            self._query_frame.update_channels()
        if pkg.toolchain:
            self.controller.select_platform_toolchain(str(pkg.toolchain))
            self._query_frame.update_toolchains()


    # Navigates to another package, remembering the current query text and
    # channel/toolchain so go_back() can return to it. Clears the forward
    # history, like a browser.
    def navigate_to_package(self, query_text: str):
        self._history.append(self._capture_nav_state())
        self._forward.clear()
        self._query_frame.set_back_enabled(True)
        self._query_frame.set_forward_enabled(False)
        self.query(text=query_text)


    # Initiates a version-range diff query for pkg_name between version_from and version_to.
    def navigate_to_compare(self, pkg_name: str, version_from: str, version_to: str):
        self.navigate_to_package(f'{pkg_name}-{version_from}..{version_to}')


    # 'Swap versions' button handler - re-issues the current diff query with prev/cur reversed.
    def swap_compare_versions(self):
        if not self.controller.diff_mode or not self.controller.cmp_entries:
            return

        root_cmp = self.controller.cmp_entries[0][0]
        pkg_prev = root_cmp.pkg_a
        pkg_cur = root_cmp.pkg_b
        if not pkg_prev or not pkg_cur:
            return

        self.navigate_to_compare(pkg_cur.name, pkg_cur.version, pkg_prev.version)


    # Like navigate_to_package(), but for an already-known Package - see
    # query()'s pkg parameter for why this avoids the ambiguous string
    # round-trip.
    def navigate_to_package_exact(self, pkg: Package):
        self._history.append(self._capture_nav_state())
        self._forward.clear()
        self._query_frame.set_back_enabled(True)
        self._query_frame.set_forward_enabled(False)
        self._apply_package_context(pkg)
        self.query(pkg=pkg)


    # Appends pkg to the shared active_deps document (skipping exact
    # duplicates - Package.__eq__ compares by str()) and notifies the owner
    # (RBBuildGuiApp.refresh_active_deps()) so other views of the same
    # document (the sidebar) pick up the change.
    def add_to_deps(self, pkg: Package):
        if pkg in self.active_deps:
            return
        self.active_deps.append(pkg)
        if self.on_active_deps_change:
            self.on_active_deps_change()


    # True if widget is deps_drop_target or one of its descendants - used by
    # PkqPackagesTreeFrame's drag-and-drop to decide whether a release point
    # counts as a drop onto the Active Deps sidebar.
    def is_deps_drop_target(self, widget: Optional[QWidget]) -> bool:
        if self.deps_drop_target is None:
            return False
        while widget is not None:
            if widget == self.deps_drop_target:
                return True
            widget = widget.parentWidget()
        return False


    # Returns to the previous query, pushing the current query onto the forward history.
    def go_back(self, event=None):
        if not self._history:
            return
        self._forward.append(self._capture_nav_state())
        state = self._history.pop()
        self._query_frame.set_back_enabled(bool(self._history))
        self._query_frame.set_forward_enabled(True)
        self._restore_nav_state(state)
        self.query(text=state.query_text, record_history=False)


    # Re-applies a query previously undone by go_back().
    def go_forward(self, event=None):
        if not self._forward:
            return
        self._history.append(self._capture_nav_state())
        state = self._forward.pop()
        self._query_frame.set_forward_enabled(bool(self._forward))
        self._query_frame.set_back_enabled(True)
        self._restore_nav_state(state)
        self.query(text=state.query_text, record_history=False)


    # Browser-style 'Home' button: navigates to the unfiltered package listing.
    def go_home(self, event=None):
        self.navigate_to_package('')


    # Handles one (kind, item, depth) progress payload from the background
    # thread, streaming rows into the tree as they arrive. The final render
    # still happens in on_success() -> display_packages().
    def _on_query_progress(self, payload):
        kind, item, depth = payload
        if not self._streaming_started:
            self._streaming_started = True
            if kind == 'entry':
                self._tree_frame.begin_streaming(self._filter_frame.txt, self._filter_frame.collapse, self._filter_frame.problems)
            else:
                self._tree_frame.begin_streaming_compare(self._filter_frame.enabled_states)

        if kind == 'entry':
            self._tree_frame.append_entry(item, depth)
        else:
            self._tree_frame.append_compare_entry(item, depth)

        self._progress_count += 1
        self.status_busy(f'Querying ... ({self._progress_count} found)')


    # Formats a Package for display in the query text box: plain
    # 'name-version', falling back to 'name@version' only when the name
    # itself contains a '-'.
    @staticmethod
    def _display_text(pkg: Package) -> str:
        if not pkg.version:
            return pkg.name
        if '-' in pkg.name:
            return f'{pkg.name}@{pkg.version}'
        return f'{pkg.name}-{pkg.version}'


    def display_packages(self):
        self._tree_frame.display_packages(self._filter_frame.txt, self._filter_frame.collapse, self._filter_frame.problems, self._filter_frame.enabled_states)
        has_tree = self.controller.current_root_package is not None
        self._filter_frame.set_diff_mode(self.controller.diff_mode, has_tree=has_tree)


    # Relays a profile change from the query bar to the caller - switching
    # profile requires a full DI container rebuild, which PkqView/PkqController
    # cannot do to themselves.
    def change_profile(self, profile_name: str):
        if self.on_profile_change:
            self.on_profile_change(profile_name)


    # Shows the properties panel only when a package with a pinned version is selected.
    def update_properties(self):
        pkg = self.controller.package
        if pkg and pkg.version:
            self._properties_frame.show()
            self._properties_frame.update_all()
        else:
            self.clear_properties()


    def clear_properties(self):
        self._properties_frame.hide()
        self._properties_frame.clear_all()


    # Guarded by _busy so repeated calls (e.g. once per streamed progress
    # row) don't push multiple override cursors that status_ready() would
    # then fail to fully unwind, leaving the wait cursor stuck forever.
    def status_busy(self, message: str = ''):
        if not self._busy:
            self._busy = True
            QApplication.setOverrideCursor(Qt.WaitCursor)
        self.status_label.setText(message)
        QApplication.processEvents()


    def status_ready(self):
        if self._busy:
            self._busy = False
            QApplication.restoreOverrideCursor()
        self.status_label.setText('')
        QApplication.processEvents()


    # Indeterminate progress bar until set_progress() or hide_progress() is called.
    def show_progress(self):
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)


    # Switches to determinate mode and sets the given percentage (0-100).
    def set_progress(self, pct: float):
        if self.progress_bar.minimum() == 0 and self.progress_bar.maximum() == 0:
            self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(int(pct))


    def hide_progress(self):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
