# SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
# SPDX-FileContributor: Tolga Dalman
#
# SPDX-License-Identifier: MIT

import functools
import os
import re
import shutil
import subprocess
import sys

from pathlib import Path
from typing import List

from rbbuild.core.paths import Paths
from rbbuild.core.runtime_settings import RuntimeSettings
from rbbuild.core.toolchain import Toolchain
from rbbuild.librbb.crypto import compute_sha1sum
from rbbuild.librbb.term import term
from rbbuild.package.component import Component
from rbbuild.package.metadata import Metadata
from rbbuild.package.package import Package


# For the different generators, we need to pass specific parameters to the
# cmake command (after cmake --build --). This is, what this class does.
class MakeTool:
    def __init__(
        self,
        settings: RuntimeSettings,
        paths: Paths,
        toolchain: Toolchain,
        cmake_generator: str,
    ):
        self.paths = paths
        # Ninja need to set the debug mode at setup time
        self.setup_args = []
        # IDEs (Visual Studio) allow to set the debug config at build time
        self.build_config_switch = None

        self.cmake_generator = cmake_generator

        # For Visual Studio, we need to pass -A <Win32|x64>
        self.vs_architecture = None
        if toolchain.name.startswith('visualstudio'):
            self.executable = Path('visualstudio')   # TODO: this is a fake and not used

            self.verbose_switch = '/v:n'
            self.njobs_switch = '/maxcpucount:'
            self.build_config_switch = '%s' % ('Release' if not settings.op_mode.debug else 'Debug')
            if toolchain.name.endswith('-x64'):
                self.vs_architecture = 'x64'
            else:
                self.vs_architecture = 'Win32'
        else:
            if cmake_generator == 'Ninja':
                self.executable = Path('ninja')    # TODO: needs refactoring ...
                # Ninja
                self.verbose_switch = '-v'
            else:
                # Makefiles
                self.verbose_switch = 'VERBOSE=1'
            self.njobs_switch = '-j '
            self.setup_args = [f'-DCMAKE_BUILD_TYPE={"DEBUG" if settings.op_mode.debug else "RELEASE"}']


    @property
    def available_targets(self) -> List[str]:
        argv = ['ninja', '-t', 'targets']
        proc = subprocess.run(
            argv,
            bufsize=0,
            cwd=self.paths.build,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        targets = []
        for line in proc.stdout.split():
            if ':' in line:
                targets.append(line.split(':', maxsplit=1)[0].strip())

        return targets


class CMake:
    def __init__(
        self,
        settings: RuntimeSettings,
        paths: Paths,
        maketool: MakeTool,
        cmake_config: dict,
        metadata: Metadata,
    ):
        self.settings = settings
        self.paths: Paths = paths
        self.maketool = maketool
        self.cmake_config = cmake_config if cmake_config else {}
        self.metadata = metadata


    @functools.cached_property
    def cmake_executable(self):
        found = shutil.which('cmake')
        if found is None:
            # Fall back to the directory of the running interpreter (venv)
            found = shutil.which('cmake', path=str(Path(sys.executable).parent))
        return found


    @property
    def cmake_path(self) -> Path:
        from rbbuild import data_path
        return data_path() / 'cmake'


    @property
    def cmakefiles(self) -> Path:
        return self.paths.build / 'CMakeFiles'


    @property
    def cmake_properties(self) -> Path:
        return self.paths.build / 'generated' / 'cmake.properties'


    # TODO: this needs a little bit refactoring:
    # Instead of passing the Toolchain object, we should encapsulate the
    # generator into "MakeTool".
    # However, this doesn't really all fit together, unless we invest more
    # effort. For the moment, this is good enough, but we can improve here!
    @property
    def cmake_generator(self) -> str:
        vs_gen_map = { 'visualstudio-2010': 'Visual Studio 10 2010',
                       'visualstudio-2015': 'Visual Studio 14 2015',
                       'visualstudio-2017': 'Visual Studio 15 2017',
                       'visualstudio-2019': 'Visual Studio 16 2019',
                       'visualstudio-2022': 'Visual Studio 17 2022' }

        # Note that CMake changed the Architecture selection with the parameter -A <Win32|x64|...>
        # We check for the rbbuild tcid suffix -x64 to compile 64-bit (x64), otherwise we default to 32-bit (Win32)

        # We need to pass the Visual Studio generator to CMake (cmake -G)
        # Example: visualstudio-2010=Visual Studio 10 2010
        if self.settings.toolchain.name.startswith('visualstudio'):
            # visualstudio-20xx and visual-studio-20xx-x64 map to the same Visual Studio Generator.
            # Strip -x64 if present.
            gen = self.settings.toolchain.name
            if gen.endswith('-x64'):
                gen = gen[:-len('-x64')]
            return vs_gen_map[gen]

        # Usually Ninja
        return self.maketool.cmake_generator


    @property
    def available(self) -> bool:
        return (self.paths.source / 'CMakeLists.txt').exists()


    # For some obscure reason, we need to replace all '\' in
    # CMAKE_STAGING_PREFIX and CMAKE_MODULE_PATH to ordinary '/'. All other path
    # variables that have backslashes seem to work on Windows, though.
    @property
    def install_prefix_string(self) -> str:
        install_prefix_string = str(self.paths.install_prefix)
        if sys.platform == 'win32':
            install_prefix_string = install_prefix_string.replace('\\', '/')
        return install_prefix_string



    def setup(self, install_prefix: Path):
        if not self.available:
            raise FileNotFoundError('CMakelists.txt not found')

        toolchain = self.settings.toolchain
        if not (toolchain.cmake_file and toolchain.cmake_file.is_file()):
            raise RuntimeError(
                f'Toolchain {toolchain} has no CMake toolchain file and '
                'cannot be used to build CMake projects. Select a toolchain '
                'with -t (rbbuild -l lists them).')

        # setup CMake arguments
        argv = [self.cmake_executable]
        argv.extend(['-G', self.cmake_generator])

        # Visual Studio Architecture
        if self.maketool.vs_architecture:
            argv = argv + ['-A', self.maketool.vs_architecture]

        if not self.settings.op_mode.verbose:
            argv.append('--no-warn-unused-cli')

        argv.append(f'-DCMAKE_TOOLCHAIN_FILE={self.settings.toolchain.cmake_file}')

        # The Python executable of the toolchain is exact; CMake's FindPython
        # would otherwise search registered/system interpreters
        python = self.settings.toolchain.python_path
        if python:
            argv.append(f'-DPython3_EXECUTABLE={python.as_posix()}')

        # Note that we intentionally set the staging prefix to the install
        # prefix. In future, we may want to explicitly distinguish between
        # those two variables.
        argv.append(f'-DCMAKE_STAGING_PREFIX={self.install_prefix_string}')

        _staging_mod_path = '/'.join([self.install_prefix_string, 'cmake'])

        # TODO: For some obscure reason, we need to replace all '\' in
        # CMAKE_MODULE_PATH to ordinary '/'. All other path variables that have
        # backslashes seem to work on Windows, though.
        # Problem occurs with CMake 3.8.0.
        _cmake_mod_path = str(self.cmake_path / 'modules').replace('\\','/')

        argv.append(f'-DCMAKE_MODULE_PATH={_cmake_mod_path};{_staging_mod_path}')
        argv.extend(self.maketool.setup_args)
        argv.append(str(self.paths.source))

        # -D...
        if 'cmake_defines' in self.cmake_config:
            argv.extend([f'-D {d}' for d in self.cmake_config['cmake_defines']])

        if self.settings.op_mode.verbose:
            term.info(f'Source path: {self.paths.source}')
            term.info(f'Build path: {self.paths.build}')
            term.info(f'Build commands: {argv}')

        self.paths.build.mkdir(parents=True, exist_ok=True)

        proc = subprocess.run(argv, bufsize=0, env=self.metadata.environ, cwd=self.paths.build)
        if proc.returncode != 0:
            raise RuntimeError(f'Command failed with error code {proc.returncode}:\n  {" ".join(argv)}')


    def make(self, make_target, njobs=None):
        if not self.cmakefiles.exists():
            raise FileNotFoundError(f'{self.cmakefiles} not found. Run setup first.')

        # Check whether requested target is available
        # TODO: add support for VisualStudio
        if self.maketool.executable.name == 'ninja':
            available_targets = self.maketool.available_targets
            if make_target and make_target not in available_targets:
                error_message = f'Unknown build target "{make_target}".'
                if make_target == 'package':
                    error_message +=  f' Did you define {term.bright_white("RBPackage()")} and {term.bright_white("install()")} statements in CMakeLists.txt?'
                raise RuntimeError(error_message)

        argv = [ self.cmake_executable, '--build', str(self.paths.build) ]
        if make_target:
            argv = argv + ['--target', make_target]

        # Generators for IDEs, such as Visual Studio, support multiple build
        # configurations. For switching between Debug and Release, we need to
        # pass --config Release|Debug.
        if self.maketool.build_config_switch:
            argv = argv + ['--config', self.maketool.build_config_switch]

        argv.append('--')

        # -j <njobs>
        if njobs:
            argv.append(self.maketool.njobs_switch + str(njobs))

        # -v
        if self.settings.op_mode.verbose:
            argv.append(self.maketool.verbose_switch)
            term.info(f'Build path: {self.paths.build}')
            term.info(f'Build commands: {argv}')

        proc = subprocess.run(
            argv,
            bufsize=0,
            env=self.metadata.environ,
            cwd=self.paths.build,
        )
        if proc.returncode != 0:
            raise RuntimeError(f'Command failed with error code {proc.returncode}:\n  {" ".join(argv)}')

        return proc.stdout


    def build(self, target: str=None, njobs=None):
        if not self.available:
            return

        self.make(target, njobs=njobs)


    def package(self, mypkg: Package):
        if not self.available:
            return

        self.make('package', njobs=1)
        components = self._package_components()
        mypkg.components.extend(components)


    # Reads cmake.properties and returns Package.components dict
    def _package_components(self) -> List[Component]:
        components = []
        if not self.cmake_properties.exists():
            raise FileNotFoundError(f'File not found: {self.cmake_properties}')

        with open(self.cmake_properties, 'r') as props:
            for line in props:
                if not line.startswith('subcomponent.'):
                    continue
                _, subcomp, rest = line.split('.', maxsplit=2)
                suffix, filepath = rest.split('=', maxsplit=1)
                filepath = Path(filepath.strip())

                if filepath.is_absolute():
                    # On Windows, we can have different syntax for the actual path,
                    # e.g., C:\\path vs C:/path. This is fixed by using Path().resolve().
                    if not str(filepath.resolve()).startswith(str(self.paths.source.resolve())):
                        raise FileNotFoundError('RBPACKAGE_CUSTOM_ARTIFACTS: absolute path to file must be specified inside the top-level source directory. Did you mean a relative path?\n\t%s' % (str(filepath)))
                    path = str(filepath)[len(str(self.paths.source)) + 1 : -len(str(filepath.name))]
                else:
                    path = str(filepath.parent)
                    filepath = self.paths.source / filepath

                if filepath.exists():
                    checksum = compute_sha1sum(filepath)
                else:
                    checksum = ''

                # CPack (CMake <3.8.0) bug: https://gitlab.kitware.com/cmake/cmake/-/issues/16516
                # As a workaround, we rename the file manually.
                filename = filepath.name
                if subcomp == 'default' and suffix != 'rpm':
                    filename = re.sub(r'^(.*)-default\.(%s)$' % suffix, r'\1.\2', filename)
                    if filepath.exists():
                        filepath.rename(filepath.parent / filename)
                        term.info(f'[{term.green("*")}] Renamed {filepath.name} \u2192 {filename}')

                components.append(
                    Component(
                        name      = subcomp,
                        suffix    = suffix,
                        filename  = filename,
                        checksum  = checksum,
                        localpath = path,
                    )
                )

        return components


    def install(self):
        # Even if we do not use component install, we need to set the install
        # prefix. Hence, we call cmake_install.cmake instead of 'make install'.
        cmake_install = self.paths.build / 'cmake_install.cmake'
        if not cmake_install.exists():
            raise RuntimeError('Missing cmake_install.cmake. Run setup and build first.')

        argv = [self.cmake_executable]
        # Generators for IDEs, such as Visual Studio, support multiple build
        # configurations. For switching between Debug and Release, we need to
        # pass --config Release|Debug.
        if self.maketool.build_config_switch:
            argv = argv + [ '--config', self.maketool.build_config_switch,
                            f'-DBUILD_TYPE={self.maketool.build_config_switch}' ]
        # -v
        if self.settings.op_mode.verbose:
            argv.append(self.maketool.verbose_switch)
            term.info(f'Build path: {self.paths.build}')
            term.info(f'Build commands: {argv}')

        if not self.settings.filtered_components:
            # Order of arguments is important. -P... must be defined last!
            argv = argv + [ f'-DCMAKE_INSTALL_PREFIX={self.install_prefix_string}',
                            '-P', str(cmake_install) ]

            proc = subprocess.run(
                argv,
                bufsize=0,
                env=self.metadata.environ,
                cwd=self.paths.build,
            )
            if proc.returncode != 0:
                raise RuntimeError(f'Command failed with error code {proc.returncode}:\n  {" ".join(argv)}')
        else:
            for comp in self.settings.filtered_components:
                # Order of arguments is important. -P... must be defined last!
                argv = argv + [ f'-DCMAKE_INSTALL_PREFIX={self.install_prefix_string}',
                                f'-DCOMPONENT={comp}',
                                '-P', str(cmake_install) ]

                proc = subprocess.run(
                    argv,
                    bufsize=0,
                    env=self.environ,
                    cwd=self.paths.build,
                )
                if proc.returncode != 0:
                    raise RuntimeError(f'Command failed with error code {proc.returncode}:\n  {" ".join(argv)}')


    # Search path for Sonar. Set by CMakeLists to cwd by default
    # or RBB_PACKAGE_SOURCES
    def _package_source_paths(self):
        if not self.cmake_properties.exists():
            raise FileNotFoundError('cmake properties not found: {self.cmake_properties}')

        package_sources = None
        with open(self.cmake_properties, 'r') as props:
            for line in props:
                line = line.strip()
                if line.startswith('package_sources') and '=' in line:
                    package_sources = line.split('=', maxsplit=1)[1].split(';')
                    break

        package_sources_filtered = []
        if package_sources:
            for srcdir in package_sources:
                if not srcdir:
                    continue
                if not os.path.isabs(srcdir):
                    srcdir = str(self.paths.source / srcdir)
                package_sources_filtered.append(srcdir)
        return package_sources_filtered

