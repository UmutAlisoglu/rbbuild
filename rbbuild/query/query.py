# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

from typing import Callable, Dict, List, Optional, Tuple

from copy import copy

from rbbuild.core.channel import Channel
from rbbuild.core.runtime_settings import OperationMode
from rbbuild.core.toolchain import Toolchain
from rbbuild.deps.parser import DepsParser
from rbbuild.package.diff import CompareResult, PackageDiff
from rbbuild.package.package import Package
from rbbuild.resolver.resolver import Resolver
from rbbuild.service.repository.manager import RepositoryManager


# UI-agnostic package query business logic used by both the pkq
# CLI (rbbuild/pkq.py) and the pkq GUI (rbbuild/ui/pkq/control.py).
class Query:

    def __init__(
        self,
        repoman: RepositoryManager,
        resolver: Resolver,
        deps_parser: DepsParser,
        package_diff: PackageDiff,
        op_mode: OperationMode,
    ):
        self.repoman = repoman
        self.resolver = resolver
        self.deps_parser = deps_parser
        self.package_diff = package_diff
        self.op_mode = op_mode

        self._diff_mode: bool = False
        self._entries: List[Tuple[Package, int]] = []
        self._cmp_entries: List[Tuple[CompareResult, int]] = []
        self._conflicts: Dict[str, str] = {}
        self._resolved_root: Optional[Package] = None


    @property
    def diff_mode(self) -> bool:
        return self._diff_mode


    # Flat, depth-first (Package, depth) list for the currently resolved tree.
    # depth 0 is the queried package itself.
    @property
    def entries(self) -> List[Tuple[Package, int]]:
        return self._entries


    # The pinned package whose dependency tree is currently displayed, or
    # None for a version/name listing.
    @property
    def current_root_package(self) -> Optional[Package]:
        return self._resolved_root


    # Flat, depth-first (CompareResult, depth) list for the currently
    # resolved "changes" (pkgA..pkgB) comparison.
    @property
    def cmp_entries(self) -> List[Tuple[CompareResult, int]]:
        return self._cmp_entries


    @property
    def conflicts(self) -> Dict[str, str]:
        return self._conflicts


    # Every other published version of pkg's package, newest first. Prefers
    # versions already shown in the current view over an unconstrained repo fetch.
    def other_versions(self, pkg: Package, channel: Channel) -> List[str]:
        if not pkg or not pkg.name:
            return []

        versions = self._other_versions_from_current_entries(pkg)
        if versions is None:
            versions = self._other_versions_from_repo(pkg, channel)
        return versions


    # Other versions of pkg's package already present in self._entries, or
    # None if the current display isn't a flat version listing of that package.
    def _other_versions_from_current_entries(self, pkg: Package) -> Optional[List[str]]:
        if self._diff_mode or len(self._entries) < 2:
            return None
        if any(depth != 0 for _, depth in self._entries):
            return None
        if any(entry.name != pkg.name for entry, _ in self._entries):
            return None

        versions = []
        for entry, _ in self._entries:
            if entry.version and entry.version != pkg.version and entry.version not in versions:
                versions.append(entry.version)
        return versions


    # Unconstrained fallback for other_versions(): fetches every published
    # version of pkg's package directly from the repo.
    def _other_versions_from_repo(self, pkg: Package, channel: Channel) -> List[str]:
        pkg_channel = pkg.channel or channel
        versions = []
        for candidate in self.repoman.search_versions(pkg=Package(name=pkg.name), channel=pkg_channel):
            if candidate.version and candidate.version != pkg.version and candidate.version not in versions:
                versions.append(candidate.version)
        return versions


    # Queries a package by text or package object and fills internal variables (e.g, _entries).
    # text is a plain package string or a "<pkgA>..<pkgB>" range.
    # pkg is an already-known Package instead of a parsed query string.
    #
    # There are four query modes implemented:
    # * Mode 1: list all package names                       (_query_all_packages)
    # * Mode 2: list versions of a package                   (_query_versions)
    # * Mode 3: display package tree for a specific version  (_query_pinned)
    # * Mode 4: changes between two versions                 (_query_changes)
    def query(
        self,
        *,
        text: str = None,
        pkg: Package = None,
        channel: Channel,
        toolchain: Toolchain,
        report_progress: Callable,
    ):
        self._diff_mode = False
        self._entries = []
        self._cmp_entries = []
        self._conflicts = {}
        self._resolved_root = None

        if pkg is not None:
            if pkg.version:
                self._query_pinned(channel, toolchain, report_progress, pkg=pkg)  # Mode 3
            else:
                self._query_versions(channel, report_progress, pkg=pkg)           # Mode 2
        elif not text:
            self._query_all_packages(channel, report_progress)                    # Mode 1
        elif '..' in text:
            self._query_changes(text, channel, report_progress)
        elif '-' in text and not text.endswith('@') or '@' in text:
            self._query_pinned(channel, toolchain, report_progress, text=text)    # Mode 3
        else:
            self._query_versions(channel, report_progress, text=text)             # Mode 2


    def _query_all_packages(self, channel: Channel, report_progress: Callable):
        entries = []
        for pkgname in self.repoman.list_package_names(channel=channel):
            pkg = Package(name=pkgname)
            entries.append((pkg, 0))
            report_progress(('entry', pkg, 0))
        self._entries = entries


    # Collects a flat, depth-0 list of every version yielded by candidates.
    def _collect_versions(self, candidates, label: str, report_progress: Callable):
        entries = []
        for pkg in candidates:
            entries.append((pkg, 0))
            report_progress(('entry', pkg, 0))
        if not entries:
            raise LookupError(f'Could not find package {label}')
        self._entries = entries


    # Listing versions only needs name+version, not the full manifest
    def _query_versions(self, channel: Channel, report_progress: Callable, *, text: str = None, pkg: Package = None):
        label = text or str(pkg) if pkg else ''
        candidates = self.repoman.search_versions(deps_item=text, pkg=pkg, channel=channel)
        self._collect_versions(candidates, label, report_progress)


    # Resolves a pinned-version package's dependency tree, defaulting an
    # unset toolchain to the currently selected one - or, if the toolchain
    # is still unset (e.g. none selected), lists every published toolchain
    # variant for the user to pick.
    def _query_pinned(
        self,
        channel: Channel,
        toolchain: Toolchain,
        report_progress: Callable,
        *,
        text: str = None,
        pkg: Package = None,
    ):
        if pkg is None:
            pkg = self.deps_parser.parse_item(text)
            if not pkg:
                raise LookupError(f'Could not find package {text}')

        if not pkg.toolchain:
            pkg.toolchain = toolchain

        if pkg.toolchain:
            candidates = list(self.repoman.search(pkg=pkg, channel=channel))
            if not candidates:
                raise self._toolchain_not_found_error(pkg, channel)
            self._resolve_package_tree(iter(candidates), str(pkg), report_progress)
            return

        variants = list(self.repoman.search_toolchains(pkg=pkg, channel=channel))
        if not variants:
            raise LookupError(f'Could not find package {pkg!s} for any configured toolchain')
        if len(variants) == 1:
            self._resolve_package_tree(iter(variants), str(pkg), report_progress)
        else:
            self._collect_versions(variants, str(pkg), report_progress)


    # Builds a LookupError for a toolchain-pinned package that wasn't found -
    # lists every other toolchain the same name+version IS published for (if
    # any), so the user doesn't have to guess/retry blindly.
    def _toolchain_not_found_error(self, pkg: Package, channel: Channel) -> LookupError:
        probe = copy(pkg)
        probe.toolchain = None
        available = [
            str(candidate.toolchain)
            for candidate in self.repoman.search_toolchains(pkg=probe, channel=channel)
            if candidate.toolchain
        ]

        if available:
            return LookupError(
                f'Could not find package {pkg!s} for toolchain {pkg.toolchain!s}. '
                f'Available for toolchain(s): {", ".join(available)}'
            )
        return LookupError(f'Could not find package {pkg!s}')


    # Resolves the first candidate from candidates into a full dependency tree.
    def _resolve_package_tree(self, candidates, label: str, report_progress: Callable):
        root = next(candidates, None)
        if not root:
            raise LookupError(f'Could not find package {label}')

        entries = [(root, 0)]
        report_progress(('entry', root, 0))

        for child, depth in self.resolver.walk_deps_with_count(root):
            entries.append((child, depth + 1))
            report_progress(('entry', child, depth + 1))

        self._entries = entries
        self._resolved_root = root

        self._conflicts = self.resolver.collect(this=root, pkg_in=root).conflicts


    def _query_changes(self, query_text: str, channel: Channel, report_progress: Callable):
        prev_str, cur_str = self.deps_parser.parse_deps_range(query_text)
        pkg_prev = next(self.repoman.search(deps_item=prev_str, channel=channel), None)
        pkg_cur = next(self.repoman.search(deps_item=cur_str, channel=channel), None)
        if not pkg_prev or not pkg_cur:
            raise LookupError(f'Could not find package {prev_str} / {cur_str}')

        cmp_res = self.package_diff.compare(pkg_prev, pkg_cur, traverse_deps=self.op_mode.transitive)

        self._diff_mode = True
        self._cmp_entries = self._flatten_compare(cmp_res, report_progress=report_progress)


    def _flatten_compare(self, cmp_res: CompareResult, report_progress: Callable, depth: int = 0) -> List[Tuple[CompareResult, int]]:
        entries = [(cmp_res, depth)]
        report_progress(('compare', cmp_res, depth))
        for child in cmp_res.dependencies or []:
            entries.extend(self._flatten_compare(child, report_progress, depth + 1))
        return entries


    # Downloads (or fetches from cache) all components of pkg and returns
    # the local path of the one matching filename.
    def download_package(self, pkg: Package, filename: str, progress_cb: Optional[Callable[[int, int], None]] = None) -> Optional[str]:
        if not pkg:
            return None
        for component in self.repoman.download(pkg, progress_cb=progress_cb):
            if component.filename == filename:
                return str(component.localpath)
        return None
