# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import Callable, List, Optional, Tuple

from rbbuild.container.application import Application
from rbbuild.core.toolchain import Toolchain
from rbbuild.librbb.term import term
from rbbuild.package.diff import CompareResult
from rbbuild.package.package import Package
from rbbuild.query.query import Query
from rbbuild.service.ci.manager import CIManager
from rbbuild.service.issuetracker.issuetracker_manager import IssueTrackerManager
from rbbuild.service.repository.manager import RepositoryManager
from rbbuild.service.scm.manager import SCMManager
from rbbuild.ui.pkq.history import PkqHistory


# GUI-specific layer for the pkq GUI, bridging the Qt view classes
# with the rbbuild v6 dependency-injection container. Query business logic
# itself lives in rbbuild.query.Query, shared with the pkq CLI (pkq.py).
# See documentation/developer-manual/gui_architecture.md.
class PkqController:

    DEFAULT_TOOLCHAIN = '<default>'  # virtual dropdown entry restoring the platform's default toolchain


    def __init__(self, application: Application, args):
        self.application = application
        self.args = args
        self.verbose: bool = getattr(args, 'verbose', False)

        self._selected_idx: Optional[int] = None

        # Snapshot of the toolchain computed from the platform, before any dropdown override.
        self._startup_toolchain_id: str = str(self.application.core.toolchain())

        self.history = PkqHistory(Path(self.application.config.paths.user_config()))


    # --- services ---

    @property
    def query_service(self) -> Query:
        return self.application.query.query()


    @property
    def repoman(self) -> RepositoryManager:
        return self.application.service.repository.repoman()


    @property
    def scmman(self) -> SCMManager:
        return self.application.service.scm.scmman()


    @property
    def issueman(self) -> IssueTrackerManager:
        return self.application.service.issuetracker.issueman()


    @property
    def ciman(self) -> CIManager:
        return self.application.service.ci.ciman()


    # --- profile ---

    # All discovered profile names.
    @property
    def profiles(self) -> List[str]:
        return sorted(self.application.config.profiles() or {})


    @property
    def profile(self) -> str:
        return self.application.config.settings.profile()


    @property
    def channel(self):
        return self.application.core.channel()


    @property
    def channels(self) -> List[str]:
        channels_config = self.application.config.profile.channels() or {}
        return sorted(channels_config.keys())


    # --- toolchain / platform switching ---

    # All configured toolchains, plus the virtual DEFAULT_TOOLCHAIN entry.
    @property
    def toolchains(self) -> List[str]:
        toolchains_config = self.application.config.profile.toolchains() or {}
        return [self.DEFAULT_TOOLCHAIN] + sorted(toolchains_config.keys())


    # Currently selected Toolchain, resolved fresh on every access.
    @property
    def toolchain(self) -> Toolchain:
        return self.application.core.toolchain()


    # platform_toolchain is one of the strings from toolchains, or DEFAULT_TOOLCHAIN.
    def select_platform_toolchain(self, platform_toolchain: str):
        if platform_toolchain == self.DEFAULT_TOOLCHAIN:
            platform_toolchain = self._startup_toolchain_id
        platform, _ = platform_toolchain.split('-', maxsplit=1)
        self.application.config.settings.platform.override(platform)
        self.application.config.settings.toolchain.override(platform_toolchain)


    def select_channel(self, chname: str):
        self.application.config.settings.channel.override(chname)


    # --- query / resolve ---

    @property
    def diff_mode(self) -> bool:
        return self.query_service.diff_mode


    # Flat, depth-first (Package, depth) list for the currently resolved tree.
    # depth 0 is the queried package itself.
    @property
    def entries(self) -> List[Tuple[Package, int]]:
        return self.query_service.entries


    # The pinned package whose dependency tree is currently displayed, or
    # None for a version/name listing.
    @property
    def current_root_package(self) -> Optional[Package]:
        return self.query_service.current_root_package


    # Flat, depth-first (CompareResult, depth) list for the currently
    # resolved "changes" (pkgA..pkgB) comparison.
    @property
    def cmp_entries(self) -> List[Tuple[CompareResult, int]]:
        return self.query_service.cmp_entries


    # Every other published version of pkg's package, newest first.
    def other_versions(self, pkg: Package) -> List[str]:
        return self.query_service.other_versions(pkg, channel=self.channel)


    # Wrapper method for Query.query()
    def query(self, *, text: str = None, pkg: Package = None, report_progress: Callable) -> bool:
        try:
            self.query_service.query(
                text=text,
                pkg=pkg,
                channel=self.channel,
                toolchain=self.toolchain,
                report_progress=report_progress,
            )
        except Exception as e:
            term.error('failed', e)
            return False

        self._selected_idx = None
        return True


    # --- selection ---

    def set_package(self, idx: int):
        self._selected_idx = idx


    @property
    def package(self) -> Optional[Package]:
        entry = self._current_entry()
        if entry is None:
            return None
        if self.diff_mode:
            return entry.pkg_b or entry.pkg_a
        return entry


    # Only meaningful in diff mode: the "old" side of the current CompareResult.
    @property
    def package_prev(self) -> Optional[Package]:
        if not self.diff_mode:
            return None
        entry = self._current_entry()
        return entry.pkg_a if entry else None


    def _current_entry(self):
        if self._selected_idx is None:
            return None
        source = self.cmp_entries if self.diff_mode else self.entries
        try:
            return source[self._selected_idx][0]
        except IndexError:
            return None


    # --- downloads ---

    # Downloads (or fetches from cache) all components of the selected
    # package and returns the local path of the one matching filename.
    def download_package(self, filename: str, progress_cb: Optional[Callable[[int, int], None]] = None) -> Optional[str]:
        return self.query_service.download_package(self.package, filename, progress_cb=progress_cb)


    # --- problems / conflict diagnostics ---

    # True if pkg is involved in a version conflict detected by
    # Resolver.collect() during the last query().
    def is_conflicted(self, pkg: Package) -> bool:
        return repr(pkg) in self.query_service.conflicts


    def conflict_message(self, pkg: Package) -> Optional[str]:
        return self.query_service.conflicts.get(repr(pkg))
