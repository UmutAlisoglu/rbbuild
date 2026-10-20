# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import functools
import json
import os
import shutil
import sys
import subprocess

from pathlib import Path
from typing import Dict, List

from rbbuild.core.paths import Paths
from rbbuild.core.runtime_settings import RuntimeSettings

from rbbuild.librbb.crypto import compute_sha1sum
from rbbuild.librbb.term import term

from rbbuild.package.component import Component
from rbbuild.package.manifest import Manifest
from rbbuild.package.package import Package, Tool, ExternalReference
from rbbuild.package.metadata import Metadata
from rbbuild.package.sbom import SBOM, SBOMFormat

from rbbuild.resolver.resolver import Resolver

from rbbuild.service.repository.manager import RepositoryManager
from rbbuild.sourcedir.staging_folder import StagingFolder

from .deps_file import DepsFile
from .packaging import Packaging


# This class implements rbbuild-specific methods:
# fetch, install_deps, package, publish, and clean.
class RBBuild:
    def __init__(
        self,
        settings: RuntimeSettings,
        paths: Paths,
        deps_file: DepsFile,
        resolver: Resolver,
        rbbuild_config: dict,
        packaging: Packaging,
        dependencies_config: list,
        manifest: Manifest,
        repoman: RepositoryManager,
        metadata: Metadata,
        profile_supplier: dict,
    ):
        self.settings = settings
        self.paths: Paths = paths
        self.deps_file: DepsFile = deps_file
        self.resolver: Resolver = resolver
        self.manifest: Manifest = manifest
        self.repoman: RepositoryManager = repoman
        self.metadata: Metadata = metadata
        self.profile_supplier: dict = profile_supplier

        # Project configuration items
        self.rbbuild_config = rbbuild_config if rbbuild_config else {}
        self.packaging = packaging
        self.dependencies_config = dependencies_config if dependencies_config else []


    @functools.cached_property
    def dependencies(self) -> Dict[str, Dict[str, Package]]:
        # -L / --deps-line=<deps>[,<deps>...] overrides all file-based sources
        if 'deps_line' in self.rbbuild_config:
            return self.deps_file.from_string(self.rbbuild_config['deps_line'])
        # rbbuild.toml [dependencies], deps.json, or legacy deps files —
        # all normalized to a list by load_project_configuration
        return self.deps_file.from_config(self.dependencies_config)


    def setup(self, install_prefix: Path):
        if len([*self.paths.source.iterdir()]) > 0:
            self.paths.build.mkdir(parents=True, exist_ok=True)


    def fetch(self, mypkg: Package, fi_hint: bool):
        if not self.dependencies:
            if self.dependencies_config:
                term.warning('No packages found. [dependencies] is defined but contains no matching packages.')
            return

        for namespace, entries in self.dependencies.items():
            result = self.resolver.run(entries, transitive=True, skip_build_only=True)
            if result.problems:
                raise RuntimeError('\n'.join(result.problems))
            packages = result.packages
            count = len(packages)

            term.info(f'Fetching {count} package{"" if count < 2 else "s"} for toolchain "{self.settings.toolchain}" (<dest>) [/{namespace}]')
            term.print_line()

            for pkg in packages.values():
                term.info(term.bright_white(f'Downloading {str(pkg)}'))

                for comp in self.repoman.download(pkg):
                    msg = f'[{term.green("*")}] {comp.filename} ... '
                    # if the output message is too long, we try to truncate it.
                    # We are reserving 7 characters for 'success', 'cached' or 'failed'
                    if term.log_file.isatty() and len(msg) + 7 > os.get_terminal_size().columns:
                        max_len = os.get_terminal_size().columns - 7 - len(f'[{term.green("*")}] ... ')
                        if max_len > 24:
                            fname_short = comp.filename[0:int(max_len/2) - 2] + '...' + comp.filename[-(int(max_len/2) - 2):]
                            msg = f'[{term.green("*")}] {fname_short} ... '

                    term.info(msg)

                key = f'{namespace}/' if namespace else ''
                key += str(pkg)
                if pkg.toolchain:
                    key += f'@{pkg.toolchain}'
                mypkg.dependencies[key] = pkg


    def install_deps(
        self,
        mypkg: Package,
        staging_folder: StagingFolder,
        install_prefix: Path,
        fi_hint: bool,
    ):
        if not self.dependencies:
            if self.dependencies_config:
                term.warning('No packages found. [dependencies] is defined but contains no matching packages.')
            return

        for namespace, entries in self.dependencies.items():
            # Install downloaded packages
            term.info(f'Installing packages to {install_prefix} [/{namespace}]')
            term.print_line()

            result = self.resolver.run(entries, transitive=True, skip_build_only=True)
            if result.problems:
                raise RuntimeError('\n'.join(result.problems))
            packages = result.packages
            for pkgid, pkg in packages.items():
                term.info(term.bright_white(str(pkg)))
                staging_folder.install_package(
                    pkg,
                    install_prefix=install_prefix,
                    skipped_components=self.settings.skipped_components,
                    install_build_only=pkgid in result.top_level,
                )
                mypkg.dependencies[f'{namespace}/{str(pkg)}'] = pkg
            term.print_line()

        staging_folder.index_db.store()


    def build(self, target: str=None, njobs=None):
        build_scripts = self.rbbuild_config.get('build_scripts', [])
        if not build_scripts:
            build_scripts = [s.name for s in Path(self.paths.source).glob('rbbuild-build.*')]

        for build_script in build_scripts:
            if Path(build_script).is_absolute():
                raise RuntimeError(f'Only relative paths are allowed for build-scripts: {build_script}')

            self.paths.build.mkdir(parents=True, exist_ok=True)

            argv = [
                str(self.paths.source / build_script),
            ]

            # -j <njobs>
            if njobs:
                argv.extend(['-j', str(njobs)])

            if target:
                argv.append(target)

            term.info(f'Executing command: {term.cyan(" ".join(argv))}')
            proc = subprocess.run(
                argv,
                env=self.metadata.environ,
                cwd=self.paths.source,
            )
            if proc.returncode != 0:
                raise RuntimeError(f'Command failed ({term.red(str(proc.returncode))})')


    def package(self, mypkg: Package):
        # Update dependencies
        for namespace, entries in self.dependencies.items():
            result = self.resolver.run(entries, transitive=True, skip_build_only=True)
            if result.problems:
                raise RuntimeError('\n'.join(result.problems))
            for pkg in result.packages.values():
                key = f'{namespace}/' if namespace else ''
                key += str(pkg)
                if pkg.toolchain:
                    key += f'@{pkg.toolchain}'
                mypkg.dependencies[key] = pkg

        # Components
        components = self.packaging.build_components(mypkg)
        mypkg.components.extend(components)

        # Tools
        tools = self._tools()
        mypkg.tools.extend(tools)


    # Generates SBOM and writes manifest.json to disk.
    # Called by __main__.package() after every build tool has run, so that
    # components appended by other tools (e.g. pypa sdist/wheel) are captured.
    def write_manifest(self, mypkg: Package):
        # Create manifest object
        manifest_obj = self.manifest.from_package(mypkg)

        # Write SBOM
        sbom = SBOM(SBOMFormat.AUTO)
        sbom_path = self.paths.build / sbom.make_filename(mypkg)
        sbom.generate(manifest_obj)

        data = json.dumps(sbom.json, indent=4)
        with open(sbom_path, 'w') as fd:
            fd.write(data)

        # Add SBOM as component to the package
        sbom_comp = Component(
            name       = 'sbom',
            suffix     = 'json',
            filename   = sbom_path.name,
            checksum   = compute_sha1sum(sbom_path),
            localpath  = str(self.paths.build.relative_to(self.paths.source)),
            build_only = True,
        )

        mypkg.components.append(sbom_comp)

        # Regenerate manifest to include the 'sbom' component
        manifest_obj = self.manifest.from_package(mypkg)

        # Write manifest.json
        data = json.dumps(manifest_obj, indent=4)
        manifest_path = self.paths.build / self.manifest.make_filename(
            mypkg.name,
            mypkg.version,
            mypkg.toolchain,
        )
        with open(manifest_path, 'w') as fd:
            fd.write(data)

        # Create symlink to this file
        cwd = Path.cwd()
        os.chdir(self.paths.build)
        manifest_symlink = Path('manifest.json')
        manifest_symlink.unlink(missing_ok=True)
        try:
            manifest_symlink.symlink_to(manifest_path.name)
        except OSError:
            # Symlinks may require elevated privileges on Windows; fall back to a copy.
            shutil.copy(manifest_path, manifest_symlink)
        finally:
            os.chdir(cwd)


    def publish(self, pkg: Package):
        term.info(f'Publishing artifacts to channel "{pkg.channel!s}"')
        term.info(term.bright_white(str(pkg)))

        for component in self.repoman.upload(pkg):
            term.redraw_last_line(f' ... {term.green("success")}')


    def execute(self, exe: str, extra_args: List[str], install_prefix: Path):
        cmd = [self.paths.build / exe]
        if extra_args:
            cmd.extend(extra_args)
        env = os.environ.copy()
        env['PATH'] += os.pathsep.join([ str(self.paths.build),
                                         str(install_prefix) ])
        # Extend library paths:
        # * obj/<tcid>/
        # * obj/<tcid>/lib/
        # * obj/<tcid>/usr/lib/
        # * staging/<tcid>/
        # * staging/<tcid>/lib/
        # * staging/<tcid>/usr/lib/
        libs = []
        for libpath in ['.', 'lib', 'usr/lib']:
            libs.append(str(self.paths.build     / libpath))
            libs.append(str(install_prefix / libpath))
        if sys.platform == 'linux':
            env['LD_LIBRARY_PATH'] = os.pathsep.join(libs)
        else:
            env['PATH'] += os.pathsep.join([''] + libs)

        term.info(f'Calling {term.bright_white(exe)} {term.bright_white(" ".join(extra_args))}')
        term.info(f'PATH={env.get("PATH")}')
        term.info(f'LD_LIBRARY_PATH={env.get("LD_LIBRARY_PATH")}')
        proc = subprocess.run(cmd, env=env)
        if proc.returncode != 0:
            term.error('failed', 'returned with %d' % proc.returncode)


    # This method generates Package.Tool objects to identify rbbuild and the
    # selected profile for inclusion in the manifest file. The vendor of the
    # profile is the supplier defined in the profile ([profile.supplier]).
    def _tools(self) -> List[Tool]:
        from rbbuild.version import __version__

        profile_vendor = (self.profile_supplier or {}).get('name')
        if not profile_vendor:
            raise RuntimeError('Profile does not define [profile.supplier] name')

        return [
            # rbbuild as SBOM tool
            Tool(
                vendor              = 'Robert Bosch GmbH',
                name                = 'rbbuild',
                version             = __version__,
                external_references = [
                    ExternalReference(type='website', url='https://github.com/boschglobal/rbbuild'),
                ],
            ),
            # Active rbbuild profile
            Tool(
                vendor              = profile_vendor,
                name                = self.settings.profile_name,
                version             = self.settings.profile_version,
            ),
        ]
