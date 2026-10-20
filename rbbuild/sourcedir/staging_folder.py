#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import shutil
import tarfile

from pathlib import Path
from typing import List
from zipfile import ZipFile

from rbbuild.core.paths import Paths
from rbbuild.core.toolchain import Toolchain
from rbbuild.librbb.term import term
from rbbuild.package.component import Component
from rbbuild.package.package import Package, PackageInstallAction

from rbbuild.service.repository.manager import RepositoryManager
from rbbuild.sourcedir.staging_index_db import StagingIndexDB


class StagingFolder:
    def __init__(
        self,
        toolchain: Toolchain,
        index_db: StagingIndexDB,
        paths: Paths,
        repoman: RepositoryManager,
    ):
        self.toolchain = toolchain
        self.index_db = index_db
        self.index_db.load()
        self.paths = paths
        self.repoman = repoman


    def install_package(
        self,
        pkg: Package,
        install_prefix: Path,
        skipped_components: List[str],
        install_build_only: bool=True,
    ):
        dest = install_prefix
        if pkg.installdir:
            dest /= pkg.installdir

        if not dest.exists():
            dest.mkdir(parents=True, mode=0o0755)

        installed_pkg = self.index_db.data.get(repr(pkg))
        version_changed = bool(installed_pkg and installed_pkg.version != pkg.version)

        if installed_pkg:
            if version_changed:
                # Version updated: remove all previously installed components
                for component in self.repoman.download(installed_pkg):
                    term.info(f'[{term.red("-")}] {component.filename}')
                    self.uninstall_component(
                        installed_pkg, component, component.localpath, install_prefix
                    )
            else:
                # Same version: only remove components that are no longer present
                new_comps = set(pkg.components)
                comps_to_remove = set(installed_pkg.components) - new_comps
                if comps_to_remove:
                    for component in self.repoman.download(installed_pkg):
                        if component in comps_to_remove:
                            term.info(f'[{term.red("-")}] {component.filename}')
                            self.uninstall_component(
                                installed_pkg, component, component.localpath, install_prefix
                            )

        # Components already present at the current version need no action
        already_installed = set(installed_pkg.components) if (installed_pkg and not version_changed) else set()

        for component in self.repoman.download(pkg):
            if component.name in skipped_components:
                continue

            if component.build_only and not install_build_only:
                continue

            if component in already_installed:
                continue

            if version_changed:
                term.info(f'[{term.green("*")}] {component.filename} (update)', end='')
            else:
                term.info(f'[{term.green("+")}] {component.filename}', end='')

            self.install_component(pkg, component, component.localpath, install_prefix)

        self.index_db.data[repr(pkg)] = pkg


    def remove(self):
        if not self.paths.staging_root.exists():
            return

        if not self.paths.staging.exists():
            return

        def _rmtree_onerror_handler(_function, path, excinfo):
            if excinfo[0] is FileNotFoundError:
                return
            term.error('failed', f'Could not delete {path}: {excinfo[1]}')

        term.info(f'Removing {self.paths.staging} ...')
        shutil.rmtree(self.paths.staging, onerror=_rmtree_onerror_handler)

        # TODO: we assume that indexdb is located in staging/staging-indexdb.json
        if len(list(self.paths.staging.parent.iterdir())) <= 1:
            term.info(f'Removing empty folder {self.paths.staging.parent} ...')
            shutil.rmtree(self.paths.staging.parent, onerror=_rmtree_onerror_handler)
            return

        # Update staging-indexdb.json
        deleted_ids = [
            pkgid for pkgid, pkg in self.index_db.data.items()
            if str(pkg.toolchain) == str(self.toolchain)
        ]
        for pkgid in deleted_ids:
            self.index_db.data.pop(pkgid, None)
        self.index_db.store()


    def uninstall_component(
        self,
        pkg: Package,
        component: Component,
        localfile: Path,
        install_prefix: Path,
    ):
        dest = install_prefix
        if pkg.installdir:
            dest /= pkg.installdir

        is_archive = component.suffix in self.supported_archive_suffixes

        if is_archive and pkg.install_action != PackageInstallAction.COPY:
            self._uninstall_archive(localfile, dest)
        else:
            (install_prefix / localfile.name).unlink(missing_ok=True)


    def install_component(
        self,
        pkg: Package,
        component: Component,
        localfile: Path,
        install_prefix: Path,
    ):
        dest = install_prefix
        if pkg.installdir:
            dest /= pkg.installdir

        is_archive = False
        if '.' in component.filename:
            suffix = component.filename.rsplit('.', maxsplit=1)[1]
            is_archive = suffix in self.supported_archive_suffixes

        if is_archive and pkg.install_action == PackageInstallAction.DEFAULT:
            term.redraw_last_line('')
            # TODO: we need to evaluate whether this is really needed.
            # Especially for rootfs type applications, archive permission checks might be necessary.
            # In all other use cases, using tarfile.data_filter is sufficient.
            #
            # Ref: https://docs.python.org/3/library/tarfile.html#tarfile.TarFile.extraction_filter
            if localfile.suffix.lower() != '.zip':
                shutil.unpack_archive(
                    localfile,
                    dest,
                    filter=tarfile.fully_trusted_filter,
                )
            else:
                shutil.unpack_archive(localfile, dest)

        elif component.suffix in ['rpm', 'ipk', 'deb', 'sha512']:
            # default action for IPK, RPM and SHA512 is to skip
            if pkg.install_action == PackageInstallAction.DEFAULT:
                term.redraw_last_line(f' ({term.yellow("skipped")})')
                return

            term.redraw_last_line(' (copy)')
            shutil.copy(localfile, dest)
        else:
            term.redraw_last_line(' (copy)')
            shutil.copy(localfile, dest)


    def _uninstall_archive(self, fpath: Path, dest: Path):
        if not fpath.exists():
            term.warning('File not found in dist path', str(fpath))
            return

        # Retrieve list of file names in the installed archive
        files = []
        if fpath.suffix.lower() == '.zip':
            with ZipFile(fpath) as zf:
                files = zf.namelist()
        else:
            with tarfile.open(fpath) as tf:
                files = tf.getnames()

        # Iteration 1: remove regular files and get all parent folders
        parents = set()
        for f in files:
            fp = Path(f)
            file = dest / fp
            if file.is_file(follow_symlinks=False) or file.is_symlink():
                term.debug(f'removing file {file}')
                file.unlink()

            for fp_parent in fp.parents:
                parents.add(dest / fp_parent)

        # Iteration 2: remove empty folders
        for parent in sorted(parents, reverse=True):
            if parent.exists() and [*parent.iterdir()] == 0:
                parent.rmdir()


    @property
    def supported_archive_suffixes(self):
        return [ 'zip', 'gz', 'xz', 'bz2', 'lzma', 'tar.gz', 'tar.bz2', 'tar.xz', 'tgz', 'tbz2', 'txz' ]

